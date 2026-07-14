# Enterprise Data Refinery — build context

> Turns raw, hostile documents into a trustworthy structured-data product. The spine is the trust layer that decides whether AI-extracted data is good enough to ship.

## What this is

A **self-hostable pipeline that turns hostile, heterogeneous documents into trustworthy structured data.** An LLM does the extraction/mapping; the value — and the reason an enterprise would run it — is the **trust-and-ops layer wrapped around the model**: eval gates, drift detection, provenance, observability, and cost accounting.

The document domain is not fixed. A domain is a swappable **Pack**. The platform ships with three reference Packs spanning three genuinely different AI tasks, to prove it is not a one-trick pipeline.

## Why it's built this way (read before making design calls)

- **The AI is the easy 30%. The trust/ops layer is the 70% enterprises actually pay for.** Never let a change make the model call the centerpiece and the gate an afterthought. If forced to choose where to spend effort, spend it on the eval gate, drift, and provenance.
- **Fail-closed is the default.** Data that can't pass its Pack's eval checks is quarantined, never published. A pipeline that ships bad data confidently is worse than one that ships nothing.
- **Zero marginal cost.** Everything runs locally in Docker with a local model (Ollama). No paid APIs required to run or demo. The model is a pluggable adapter so "swap in Claude" is a one-line config change, not a rewrite.
- **Public and reproducible.** All reference Packs use public data, so the repo, the dashboards, and the published datasets can all be public.
- **Cloud-portable, not cloud-dependent.** Clean twelve-factor containers so the story "this lifts to ECS/Fargate trivially" is true — but the live instance costs $0 and runs on a laptop.

## Honesty constraints (do not violate)

- "Always-on" means **scheduled, runs when the host machine is up** — fine for monthly-cadence feeds. Never imply five-nines uptime.
- Drift events and gate failures shown in demos must be **real ones the system caught**, never fabricated.
- Local-14B extraction quality is the real technical gamble. The eval gate is what makes that safe: bad extraction is caught, not shipped. "Where the local model was good enough vs. where I'd escalate to Claude" is a finding to surface, not a failure to hide.

## Architecture

Pipeline (per run, per Pack):

```
schedule → fetch raw → (mapping cache hit? else LLM infers mapping/extraction)
        → apply → EVAL GATE → pass: write canonical + publish dataset
                            → fail: quarantine + alert
        → drift detector → dashboards / admin read canonical
```

Services (Docker Compose, all local/free):

| Service | Role |
|---|---|
| Dagster (webserver + daemon) | Scheduling, run history, logs, asset lineage. Free observability + half the admin surface. |
| Ollama | Local LLM (default Qwen2.5-14B or similar). Behind `LLMProvider` so Claude is swappable. |
| Postgres | Canonical + operational state. |
| App (FastAPI + HTMX) | Admin/explorer surface — server-rendered HTML via Jinja + HTMX. No JS build step, no React/Vite. |

## The Pack abstraction (core concept)

A Pack is one document domain. Adding a Pack requires **zero core changes** — that cheapness is the whole point (and the demo).

Developer tier — a Pack is a directory:

```
packs/<name>/
  pack.yaml      # name, source(s), cadence, LLM target schema ref, task type
  schema.py      # canonical target fields (Pydantic model)
  checks.py      # this Pack's eval-gate rules
  adapter.py     # discover() / fetch() — only if not using a generic source
```

`docker compose up` auto-discovers packs.

Non-engineer tier — the admin app's **"Add a source" wizard**: paste a URL / upload a sample → system runs the LLM to *propose* a schema + draft checks → user reviews/tweaks in the UI → saves, which writes the same `packs/<name>/` files. Defining a Pack by example, not by code. This is the "self-serve building blocks the ops team composes" capability — build it for real, it's the highest-leverage demo moment.

## Reference Packs (ship all three)

| Pack | AI task | Public substrate | Ops shape it proves |
|---|---|---|---|
| **extract** (flagship, deep) | Extract prose/PDF → structured facts | County building permits (PDF). Alt substrates, swappable via `pack.yaml`: FDA warning letters, SEC 8-K item text | "Read the document, pull the fields an ops person re-keys" |
| **triage** (reference) | Classify inbound free-text → category + severity + routing | CFPB consumer-complaint narratives | "Triage the inbound queue" |
| **normalize** (reference) | Reconcile heterogeneous formats → one canonical schema | USAspending contract data | "Reconcile N bespoke vendor formats" — best showcase for schema-drift + mapping cache |

Flagship gets real depth; the other two are honest reference implementations that prove genericness. Say that asymmetry out loud; don't over-polish the references at the flagship's expense.

## Data / state model (Postgres)

- `packs` — registered packs + config snapshot
- `sources` — per-source config, cadence, enabled flag
- `runs` — run lifecycle, status (ok/degraded/failed), timings
- `canonical` — published structured records; **every row carries provenance**: source_id, run_id, mapping_version, checks_passed
- `mapping_cache` — learned mapping/extraction plan per source, keyed by content/schema hash; skip the LLM on unchanged inputs
- `eval_results` — per-run check outcomes (which check, pass/fail, offending rows)
- `drift_events` — schema drift + value drift, per source over time

Drops are idempotent, keyed by `(source, drop_date, content_hash)`.

## Trust layer specifics

- **Eval gate** — a declarative check runner. Per-Pack checks: schema conformance, null-rate thresholds, value-range sanity, row-count delta vs. last drop (Release-Analyzer-style anomaly block), format/referential checks. Failures block publish + persist offending rows.
- **Drift detector** — schema drift (columns/format changed → invalidate mapping cache, trigger re-map) and value drift (distribution shift on key fields). Emits `drift_events`.
- **Provenance** — canonical records must be answerable to "which source, run, mapping version, and checks produced this row?" This is the regulated-BU / auditor story.

## Cost accounting

Track tokens per run per Pack even when using the local model, and compute a **would-be-cost** against Claude pricing. The dashboard shows "$0 local vs. $X on Claude at this volume." Mapping cache means token spend tracks real schema changes, not run count — surface that.

## Dataset publishing

On each clean (gate-passed) drop, export the canonical slice to a **GitHub data repo** and **Hugging Face Datasets** (both free, no server). Gives non-technical users the artifact without running anything, and resolves "public/useful" vs "local/zero-spend."

## Stack conventions

- Python 3.12+, `uv`, FastAPI + Pydantic v2, SQLAlchemy/Alembic for migrations.
- Server-rendered admin: FastAPI + Jinja templates + HTMX. No separate frontend build, no React/Vite. Keep CSS minimal (Tailwind via CDN or hand-rolled). The whole codebase is Python + templates.
- Dagster for orchestration. Ollama for local inference.
- Tests: pytest. **The eval checks themselves are unit-tested** (feed known-bad input → assert the gate blocks it — "tests for the thing that tests the data"). Plus adapter contract tests, one golden-file test per Pack, drift tests.
- CI: GitHub Actions, tests green before merge.
- License: permissive (MIT/Apache-2.0).

## Build order (spine-first; demoable at every checkpoint)

1. Foundations: compose skeleton, Postgres schema, Pack loader, `LLMProvider`.
2. Flagship spine: extract Pack fetch → LLM extraction → canonical in Postgres → one view. **`compose up`-able end to end.**
3. Trust layer: eval gate + quarantine + drift + provenance.
4. Orchestration: Dagster assets + schedule + degraded-run handling. **Start accumulating real drops now** — the longitudinal demo needs wall-clock time.
5. Admin app: logs, source mgmt, gate-failure browser, 3 outputs, cost readout, "Add a source" wizard.
6. Genericness: triage + normalize reference Packs.
7. Publishing + OSS polish: dataset publisher, README + demo GIF, "write your own Pack" tutorial, tests green, license.

See `tickets.md` for the ordered ticket breakdown.

## Stories this build must stay honest to

The point of the project is to earn these lines in conversation. Do not ship anything that makes one of them a lie.

- Fail-closed trust layer over LLM output (the differentiator vs. every "here's the JSON" repo).
- Local-model vs. Claude cost/quality as a made call, not a recited opinion.
- A real drift event the system caught (format changed silently → flagged, re-mapped, didn't ship garbage).
- Adding a completely different document domain = one Pack, zero core changes.
- Provenance on every record so it can defend itself to an auditor.
- A real admin/ops surface — diagnosable when it breaks, not a black box.
