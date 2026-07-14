"""Evaluation harness: extraction accuracy vs. ground truth, trust-gate precision/recall,
cost-by-model, and parallel throughput. Writes eval/results.json and renders SVG charts to
docs/assets/eval/. Uses the configured LLM provider (default ollama) for accuracy/throughput;
the gate eval is deterministic (no model)."""

from __future__ import annotations

import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import edr.models  # noqa: F401
from edr.charts import GREEN, RED, grouped_bar_chart, hbar_chart
from edr.db import Base
from edr.llm.base import CLAUDE_PRICING, get_provider
from edr.models import Canonical, Drop, Source
from edr.packs.base import RawDoc
from edr.packs.loader import discover_packs
from edr.pipeline.extract import extract_document
from edr.pipeline.gate import evaluate_drop

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "eval"
ASSETS = ROOT / "docs" / "assets" / "eval"
FIELDS = ["permit_id", "jurisdiction", "permit_type", "status", "issued_date",
          "valuation_usd", "applicant"]
NICE = {"claude-haiku-4-5": "Haiku 4.5", "claude-sonnet-5": "Sonnet 5",
        "claude-opus-4-8": "Opus 4.8"}


def _norm(v):
    if v is None:
        return ""
    if isinstance(v, int | float):
        try:
            return f"{float(v):.2f}"
        except Exception:
            return str(v).strip().lower()
    return str(v).strip().lower()


def accuracy(provider, pack, labels, docs_dir):
    correct = dict.fromkeys(FIELDS, 0)
    tin = tout = low = 0
    n = len(labels)
    for name, gt in labels.items():
        rec, lowf, res = extract_document(pack, provider, RawDoc(ref=name,
                                          content=(docs_dir / name).read_text()))
        tin += res.tokens_in
        tout += res.tokens_out
        low += int(lowf)
        for f in FIELDS:
            if _norm(rec.get(f)) == _norm(gt.get(f)):
                correct[f] += 1
    per_field = {f: 100.0 * correct[f] / n for f in FIELDS}
    return {"per_field": per_field, "overall": statistics.mean(per_field.values()),
            "n": n, "avg_tokens_in": tin / n, "avg_tokens_out": tout / n,
            "low_confidence": low}


def gate_eval():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng)()
    pack = discover_packs(ROOT / "packs")["extract"]
    src = Source(pack_name="extract", name="eval")
    db.add(src)
    db.flush()

    def drop(records, h):
        d = Drop(source_id=src.id, drop_date="2026-01-01", content_hash=h, status="pending")
        db.add(d)
        db.flush()
        for r in records:
            db.add(Canonical(drop_id=d.id, source_id=src.id, mapping_version="v1", record=r))
        db.flush()
        return d

    clean_pub = 0
    n_clean = 6
    for i in range(n_clean):
        recs = [{"permit_id": f"C{i}{j}", "valuation_usd": 100000} for j in range(8)]
        d = drop(recs, f"clean{i}")
        clean_pub += int(evaluate_drop(db, d, pack))

    base = drop([{"permit_id": f"B{j}", "valuation_usd": 5} for j in range(3)], "base")
    evaluate_drop(db, base, pack)

    violations = [
        [{"permit_id": None, "valuation_usd": 100000}],               # missing required id
        [{"permit_id": "X", "valuation_usd": -500}],                  # negative value
        [{"permit_id": "Y", "valuation_usd": None} for _ in range(3)],  # high null-rate
        [{"permit_id": "Z", "valuation_usd": "abc"}],                 # schema violation
    ]
    caught = 0
    for i, v in enumerate(violations):
        caught += int(not evaluate_drop(db, drop(v, f"viol{i}"), pack))
    spike = drop([{"permit_id": f"S{j}", "valuation_usd": 5} for j in range(30)], "spike")
    caught += int(not evaluate_drop(db, spike, pack))  # row-count anomaly vs base(3)
    n_viol = len(violations) + 1
    return {"clean_total": n_clean, "clean_published": clean_pub,
            "violation_total": n_viol, "violation_quarantined": caught}


def throughput(provider, pack, labels, docs_dir, k=6):
    names = list(labels)[:k]
    docs = [RawDoc(ref=n, content=(docs_dir / n).read_text()) for n in names]
    extract_document(pack, provider, docs[0])  # warm up
    t = time.perf_counter()
    for d in docs:
        extract_document(pack, provider, d)
    seq = time.perf_counter() - t
    t = time.perf_counter()
    with ThreadPoolExecutor(max_workers=k) as ex:
        list(ex.map(lambda d: extract_document(pack, provider, d), docs))
    par = time.perf_counter() - t
    return {"docs": k, "sequential_s": round(seq, 2), "parallel_s": round(par, 2),
            "speedup": round(seq / par, 2) if par else 0}


def costs(avg_in, avg_out):
    out = {"Local (Ollama)": 0.0}
    for m, (ri, ro) in CLAUDE_PRICING.items():
        out[NICE[m]] = round(1000 * (avg_in * ri + avg_out * ro), 2)
    return out


def _who(results):
    nice = {"claude-haiku-4-5": "Claude Haiku 4.5", "claude-sonnet-5": "Claude Sonnet 5",
            "claude-opus-4-8": "Claude Opus 4.8"}
    m = results.get("model", "")
    if results["provider"] == "ollama":
        return f"local {m}"
    return nice.get(m, m or results["provider"])


def render(results):
    ASSETS.mkdir(parents=True, exist_ok=True)
    a = results["accuracy"]
    items = [(f.replace("_", " "), round(a["per_field"][f], 1)) for f in FIELDS]
    items.append(("OVERALL", round(a["overall"], 1)))
    (ASSETS / "accuracy.svg").write_text(hbar_chart(
        "Extraction accuracy by field", items, unit="%", max_value=100,
        subtitle=f"{_who(results)} · {a['n']} labeled permit documents · exact-match"))

    g = results["gate"]
    clean_q = g["clean_total"] - g["clean_published"]
    viol_p = g["violation_total"] - g["violation_quarantined"]
    (ASSETS / "gate.svg").write_text(grouped_bar_chart(
        "Trust gate: does it catch bad data?",
        ["Clean drops", "Drops with a defect"],
        [("Published", GREEN, [g["clean_published"], viol_p]),
         ("Quarantined", RED, [clean_q, g["violation_quarantined"]])],
        subtitle="fail-closed: clean data ships, defective data is blocked", value_fmt="{:.0f}"))

    c = results["cost"]
    (ASSETS / "cost.svg").write_text(hbar_chart(
        "Cost per 1,000 documents", [(k, v) for k, v in c.items()],
        max_value=max(c.values()) * 1.15 or 1, value_fmt="${:.2f}",
        subtitle="same token volume, priced across backends — local is $0"))

    t = results["throughput"]
    (ASSETS / "throughput.svg").write_text(hbar_chart(
        f"Throughput: {t['speedup']}× faster in parallel",
        [("Sequential", t["sequential_s"]), (f"Parallel ({t['docs']} workers)", t["parallel_s"])],
        max_value=t["sequential_s"] * 1.15 or 1, value_fmt="{:.1f}s",
        subtitle=f"{t['docs']} documents · {_who(results)}"))
    print("rendered 4 charts to", ASSETS)


def main():
    labels = json.loads((EVAL / "labels.json").read_text())
    docs_dir = EVAL / "dataset"
    provider = get_provider()
    packs = discover_packs(ROOT / "packs")
    pack = packs["extract"]

    print(f"provider={provider.name} · scoring accuracy on {len(labels)} docs ...", flush=True)
    acc = accuracy(provider, pack, labels, docs_dir)
    print(f"  overall accuracy: {acc['overall']:.1f}%", flush=True)
    print("gate precision/recall ...", flush=True)
    gate = gate_eval()
    print("throughput ...", flush=True)
    tput = throughput(provider, pack, labels, docs_dir)
    cost = costs(acc["avg_tokens_in"], acc["avg_tokens_out"])

    results = {"provider": provider.name, "model": getattr(provider, "model", provider.name),
               "accuracy": acc, "gate": gate,
               "throughput": tput, "cost": cost,
               "avg_tokens": {"in": round(acc["avg_tokens_in"], 1),
                              "out": round(acc["avg_tokens_out"], 1)}}
    (EVAL / "results.json").write_text(json.dumps(results, indent=2))
    render(results)
    print("wrote eval/results.json")


if __name__ == "__main__":
    main()
