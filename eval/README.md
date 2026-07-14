# Evaluation harness

Produces the numbers and charts in the top-level README.

```bash
uv run python eval/make_dataset.py     # regenerate the labeled dataset (committed)
uv run python eval/run_eval.py         # score accuracy + gate + cost + throughput
```

`run_eval.py` uses the configured LLM provider (default `ollama`) for extraction accuracy
and throughput; the trust-gate evaluation is deterministic (no model). Results are written
to `eval/results.json` and rendered as SVG charts under `docs/assets/eval/`.

- **Accuracy** — 24 labeled permit documents in 3 formats; exact-match per field vs. ground truth.
- **Gate** — clean drops vs. drops with injected defects (missing id, negative value, high
  null-rate, schema violation, row-count spike); measures publish/quarantine correctness.
- **Cost** — same token volume priced across Local / Haiku / Sonnet / Opus.
- **Throughput** — sequential vs. parallel extraction wall-clock.
