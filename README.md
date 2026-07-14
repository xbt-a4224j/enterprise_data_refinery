# Enterprise Data Refinery

**Turn hostile, heterogeneous documents into trustworthy structured data — locally, for free.**

Most "LLM document extraction" projects stop at *here's the JSON*. The Refinery ships the part
that lets you actually run that in production: a **trust-and-ops layer** wrapped around the model —
eval gates that fail closed, drift detection, provenance on every record, observability, and
cost accounting. The model does the extraction; the Refinery decides whether the result is good
enough to publish.

The document domain is swappable. A domain is a **Pack** — some config, a target schema, and its
eval checks. It ships with three reference Packs across three different AI tasks (extract /
triage / normalize) to show it isn't a one-trick pipeline.

## Why

The LLM call is the easy 30%. The 70% that an enterprise pays for is trust: does this data
defend itself to an auditor, does it fail safely when a source silently changes format, what did
it cost, and can a non-engineer point it at a new pile of documents. That 70% is the project.

## Run it

Everything is local Docker with a local model (Ollama). No paid API required.

```bash
docker compose up
```

(Full quick start: see `tickets.md` T-001 / this README's quick-start section once built.)

Swap in a frontier model (e.g. Claude) with a one-line `pack.yaml`/env change — the model is a
pluggable provider, not a dependency.

## Packs

| Pack | AI task | Substrate |
|---|---|---|
| `extract` | prose/PDF → structured facts | county building permits (swappable) |
| `triage` | free-text → category + severity + routing | CFPB consumer complaints |
| `normalize` | heterogeneous formats → one canonical schema | USAspending contracts |

Write your own Pack: copy `packs/_template/`, define a schema and checks, `docker compose up`.
Or use the admin app's **Add a source** wizard to create one from a sample file — no code.

## Status

Early / in active build. See `tickets.md` for the roadmap.

## License

TBD (permissive — see T-029).
