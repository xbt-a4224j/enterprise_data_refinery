# Enterprise Data Refinery — tickets

Ordered, dependency-aware. Each ticket's title starts with `T-###` so issues map back here. Each has concrete acceptance criteria. Create as GitHub issues with `gh issue create` (see README).

Milestones:
- **M1 Spine** — T-001…T-008: `compose up` runs the flagship end to end.
- **M2 Trust** — T-009…T-013: nothing bad ships; drift + provenance.
- **M3 Scheduled** — T-014…T-015: runs on a schedule, accumulating real drops.
- **M4 Admin** — T-016…T-023: the ops/explorer surface + non-engineer wizard.
- **M5 Generic** — T-024…T-025: two more Packs prove genericness.
- **M6 Ship** — T-026…T-029: publishing, docs, tests, license.

---

## Epic A — Foundations

### T-001 Compose skeleton + service wiring
Bring up Postgres, Dagster (webserver + daemon), Ollama, and App (FastAPI + HTMX) as empty-but-healthy services.
- `docker compose up` starts all services; healthchecks pass.
- Ollama pulls the default model on first run (documented, one command).
- README has a "quick start" stub that actually works from a clean clone.

### T-002 Postgres schema + migrations
Alembic migrations for the full state model.
- Tables: `packs`, `sources`, `runs`, `canonical`, `mapping_cache`, `eval_results`, `drift_events`.
- `canonical` includes provenance columns: `source_id`, `run_id`, `mapping_version`, `checks_passed`.
- Drops uniquely keyed by `(source, drop_date, content_hash)`.
- `alembic upgrade head` runs clean on an empty DB in CI.

### T-003 Pack loader + abstraction
Discover and load `packs/<name>/` at startup.
- Loads `pack.yaml`, `schema.py` (Pydantic model), `checks.py`, optional `adapter.py`.
- Invalid/partial packs fail loudly with a clear error, not silently.
- A trivial example pack loads and is listed via a `packs` API/CLI call.
- Depends on: T-002.

### T-004 LLMProvider interface + Ollama & Claude impls
Pluggable model layer with cost accounting.
- `LLMProvider` interface (complete/structured-output call).
- Ollama implementation (default). Claude implementation behind config; unused unless a key is set.
- Every call records token counts and a computed would-be-Claude-cost.
- Switching provider is a `pack.yaml`/env change, no code change.
- Depends on: T-001.

---

## Epic B — Flagship Pack: extract (spine)

### T-005 extract Pack source adapter
Fetch a real public document corpus (default: county building permits, PDF).
- `discover()` lists available documents; `fetch()` returns raw bytes + metadata.
- Raw artifacts + metadata persisted; re-fetch is idempotent by content hash.
- Substrate is swappable via `pack.yaml` (document the FDA / SEC 8-K alternatives).
- Depends on: T-003.

### T-006 extract Pack extraction op
Document → canonical fields via `LLMProvider`.
- `schema.py` defines the canonical target for permits.
- Extraction handles multi-page/chunked docs; returns per-field values + a confidence signal.
- Low-confidence extractions are flagged (feeds the gate/quarantine later).
- Depends on: T-004, T-005.

### T-007 Mapping/extraction cache
Skip the LLM when input structure is unchanged.
- Learned extraction plan cached per source, keyed by content/schema hash.
- Cache hit path performs zero LLM calls (assert in a test).
- Cache invalidated on schema drift (wired in T-012).
- Depends on: T-006.

### T-008 Canonical write + idempotent drops
Persist extracted records with provenance.
- Writes to `canonical` with `source_id`, `run_id`, `mapping_version`, `checks_passed` (checks default false until T-011 gates it).
- Re-running the same drop does not duplicate rows.
- **Milestone M1:** `compose up` → one permit source flows fetch → extract → canonical, viewable via a raw SQL/API query.
- Depends on: T-006, T-002.

---

## Epic C — Trust layer

### T-009 Eval-gate framework
Declarative check runner.
- Checks declared per Pack in `checks.py`; runner executes them against a drop and records outcomes to `eval_results`.
- Each result: check name, pass/fail, offending row refs.
- Unit-tested with a known-bad fixture that must fail.
- Depends on: T-008.

### T-010 extract Pack checks
Concrete checks for the flagship.
- Schema conformance, required-field presence, null-rate threshold, value-range/format sanity, row-count delta vs. previous drop.
- Thresholds live in `pack.yaml`, not hardcoded.
- Depends on: T-009.

### T-011 Fail-closed publish gate + quarantine + alert
Bad data never becomes published canonical.
- A drop only sets `checks_passed=true` and becomes queryable-as-published if all blocking checks pass.
- Failing drops are quarantined (retained, marked, not published) and emit an alert (log sink now; optional Slack webhook via env).
- Test: a drop with an injected bad row is quarantined, and last-good published data is untouched.
- Depends on: T-010.

### T-012 Drift detector
Detect and record schema + value drift.
- Schema drift (columns/format changed) invalidates the mapping cache and triggers re-mapping.
- Value drift (distribution shift on configured key fields) recorded to `drift_events`.
- Test: a simulated format change produces a `drift_events` row and a cache invalidation.
- Depends on: T-007, T-009.

### T-013 Provenance query
Answer "what produced this row?"
- Given a canonical record, return its source, run, mapping version, and the checks it passed.
- Exposed via API (consumed by the admin gate-failure browser later).
- **Milestone M2.**
- Depends on: T-011.

---

## Epic D — Orchestration

### T-014 Dagster assets + schedule
Wrap the pipeline as scheduled assets.
- Assets: fetch → extract → gate → store → publish, with lineage visible in Dagster.
- A schedule runs the flagship on a sane cadence; retries with backoff on transient fetch/LLM errors.
- Depends on: T-011.

### T-015 Run lifecycle + degraded-run handling
Never clobber last-good data on partial failure.
- A run is marked `ok` / `degraded` / `failed`; degraded runs keep the previous published drop.
- Fetch failure, LLM failure, and gate failure each map to the correct run status.
- **Milestone M3:** scheduled runs accumulate real drops over wall-clock time.
- Depends on: T-014.

---

## Epic E — Admin / explorer app

### T-016 FastAPI app: endpoints + HTMX views
Backend and server-rendered admin in one FastAPI app.
- JSON endpoints + HTMX HTML partials for: list packs/sources, runs, live log stream, gate failures (with offending rows), canonical query, cost summary, provenance (T-013).
- Jinja templates + HTMX; no JS build step.
- Depends on: T-013.

### T-017 Token auth
Gate the admin surface (it has run controls + logs).
- Single admin token via env; unauthenticated requests to admin/control endpoints are rejected.
- Read-only dataset/explorer endpoints may be public (documented which).
- Depends on: T-016.

### T-018 App shell + logs + run history
Base layout and the operational views (Jinja + HTMX).
- Base template with nav; system-log stream page (HTMX polling/SSE); run-history view (status, timings, links to Dagster).
- Depends on: T-016.

### T-019 Source management UI
Manage packs/sources from the app.
- List sources; enable/disable; view the learned mapping/extraction plan and cadence.
- Depends on: T-018.

### T-020 Gate-failure browser
Make failures diagnosable.
- For any failed run, show which checks failed and the exact offending rows.
- Depends on: T-018.

### T-021 The three outputs
Canonical-driven views (generic, not permit-specific hardcoding).
- (a) Facts/records explorer; (b) change-over-time (longitudinal, reads `drift_events` + drop history); (c) data-quality scorecard per source over time.
- Each view is driven by canonical + eval/drift tables so it works for any Pack.
- Depends on: T-018, T-012.

### T-022 Cost readout
Show the FinOps story.
- Tokens per run per Pack; $0-local vs. would-be-Claude-cost; note that spend tracks schema changes, not run count.
- Depends on: T-016, T-004.

### T-023 "Add a source" wizard
Non-engineer Pack creation by example.
- Upload a sample / paste a URL → LLM proposes a schema + draft checks → user edits in UI → save writes `packs/<name>/` files.
- The saved pack is picked up by the loader (T-003) and runnable.
- **Milestone M4.**
- Depends on: T-019, T-006, T-009.

---

## Epic F — Genericness (reference Packs)

### T-024 triage reference Pack (CFPB complaints)
Classification task: inbound free-text → category + severity + routing.
- Adapter fetches CFPB complaint narratives; `schema.py` = category/severity/routing; `checks.py` = label-validity + distribution sanity; one output view reuses T-021.
- Zero core changes required to add it (that's the acceptance test).
- Depends on: T-023 or T-011 (whichever lands first — Pack only needs the core + gate).

### T-025 normalize reference Pack (USAspending)
Normalization task: heterogeneous formats → one canonical schema.
- Adapter fetches USAspending contract data; canonical schema + checks; exercises mapping cache + schema-drift path.
- **Milestone M5.**
- Depends on: T-012.

---

## Epic G — Publishing & OSS polish

### T-026 Dataset publisher
Publish clean drops for non-technical consumers.
- On a gate-passed drop, export the canonical slice to a GitHub data repo and Hugging Face Datasets.
- Publish is idempotent and skipped for quarantined drops.
- Depends on: T-011.

### T-027 README + "write your own Pack" tutorial + demo GIF
The OSS front door.
- README: what/why, one-command quick start, architecture diagram, the trust-layer wedge.
- A worked "write your own Pack" tutorial using one reference Pack as the example.
- A demo GIF of the running system (Dagster runs + a gate failure + a dashboard).
- Depends on: T-023, T-024.

### T-028 Test suite + CI
Green tests in CI.
- Eval-check unit tests, adapter contract tests, one golden-file test per Pack, drift tests.
- GitHub Actions runs migrations + tests on PR.
- Depends on: T-011, T-024, T-025.

### T-029 License + CONTRIBUTING + Pack template
Make contribution real.
- Permissive LICENSE; CONTRIBUTING; a `packs/_template/` scaffold a contributor can copy.
- Depends on: T-027.
