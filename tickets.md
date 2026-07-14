# Enterprise Data Refinery — tickets

Ordered, dependency-aware. Titles start with `T-###` so GitHub issues map back here. Each has
concrete acceptance criteria. Verification is local (`docker compose up` + `pytest` + a real
run); an issue is closed only after its acceptance criteria are demonstrated locally.

Milestones:
- **M1 Spine** T-001…T-020 — `compose up` runs the flagship fetch → extract → canonical.
- **M2 Trust** T-021…T-028 — nothing bad ships; drift + provenance.
- **M3 Scheduled** T-029…T-031 — runs on a schedule, accumulating real drops.
- **M4 UI** T-032…T-044 — the high-craft admin/explorer surface.
- **M5 Generic** T-045…T-046 — two more Packs prove genericness.
- **M6 Ship** T-047…T-050 — publishing, tests, docs, license.

---

## Epic A — Foundations

### T-001 Repo scaffold + tooling
- `pyproject.toml` (uv), package `edr/`, `ruff` + `pytest` configured, `Makefile` (`make dev`, `make test`, `make up`).
- `uv run pytest` runs (zero tests ok) and `ruff check` passes.
- `.gitignore`, `.env.example`.

### T-002 Docker Compose skeleton
- Services: `db` (Postgres), `ollama`, `app` (FastAPI), `dagster`.
- `docker compose up` → healthchecks green; `app` serves `/health` 200.
- Depends on: T-001.

### T-003 Settings & config
- `pydantic-settings` config from env; typed access; documented in `.env.example`.
- Missing required config fails fast with a clear message.
- Depends on: T-001.

### T-004 Structured logging + log store
- JSON structured logs; events also persisted to `log_events` for the UI stream.
- A helper emits a log and it is queryable.
- Depends on: T-003, T-005.

### T-005 Postgres schema + migrations + models
- Alembic migrations for `packs`, `sources`, `runs`, `canonical`, `mapping_cache`, `eval_results`, `drift_events`, `log_events`.
- `canonical` provenance columns: `source_id`, `run_id`, `mapping_version`, `checks_passed`.
- SQLAlchemy models + session; `alembic upgrade head` clean on empty DB.
- Depends on: T-002.

### T-006 FastAPI app bootstrap
- App factory, `/health`, Jinja + static wiring, DB session dependency, placeholder base template.
- Depends on: T-005.

---

## Epic B — Pack framework

### T-007 Pack abstraction + pack.yaml spec
- `pack.yaml` schema (name, task type, sources, cadence, target schema ref, check config) validated via Pydantic; invalid rejected with a precise error.
- Depends on: T-003.

### T-008 Pack loader + registry
- Auto-discover `packs/<name>/`; load `pack.yaml`, `schema.py`, `checks.py`, optional `adapter.py`; registry lists packs; broken pack fails loudly.
- Depends on: T-007.

### T-009 Canonical model + idempotent drops
- Canonical write path with provenance; drops keyed uniquely by `(source, drop_date, content_hash)`; re-run does not duplicate (test).
- Depends on: T-005.

### T-010 Pack template
- `packs/_template/` with commented files; copying + renaming yields a loadable no-op pack.
- Depends on: T-008.

---

## Epic C — LLM provider

### T-011 LLMProvider interface + cost accounting
- Interface: text + schema-constrained structured output; every call records tokens + computed would-be-Claude cost to the run.
- Depends on: T-003.

### T-012 Fake deterministic provider
- Test provider returning fixed structured output, zero network; default under `pytest`.
- Depends on: T-011.

### T-013 Ollama provider
- Talks to `ollama`; schema-constrained output; retries on transient errors; integration test (skipped if absent) extracts from a fixture.
- Depends on: T-011.

### T-014 Claude provider
- Config-gated; same interface; real token/cost; unit-tested with a mocked client.
- Depends on: T-011.

---

## Epic D — Flagship extract pack (spine)

### T-015 Source adapter interface + generic adapter
- `SourceAdapter` (`discover()`/`fetch()` + metadata); generic HTTP/file adapter for simple sources.
- Depends on: T-008.

### T-016 extract pack adapter + fixtures
- `packs/extract/` adapter; **sample permit docs committed as fixtures** so the pipeline runs offline/deterministically; live fetch wired but not required for tests.
- Depends on: T-015.

### T-017 extract pack canonical schema
- `schema.py` canonical permit fields (Pydantic); documented.
- Depends on: T-007.

### T-018 Document loading + chunking
- Load PDF/text fixtures; deterministic chunking to model-friendly windows.
- Depends on: T-016.

### T-019 LLM extraction op
- Document → canonical fields via `LLMProvider`; per-field values + confidence; low-confidence flagged; with fake provider produces expected rows (test).
- Depends on: T-018, T-012.

### T-020 Extraction cache + canonical write (SPINE)
- Extraction plan cached per source (content/schema hash); cache hit does zero LLM calls (test); writes canonical with provenance.
- **M1:** `docker compose up` → one permit source flows fetch → extract → canonical, viewable via API/SQL.
- Depends on: T-019, T-009.

---

## Epic E — Trust layer

### T-021 Eval-gate framework
- Declarative check runner; per-Pack `checks.py`; outcomes to `eval_results` (check, pass/fail, offending rows); known-bad fixture fails (test).
- Depends on: T-020.

### T-022 Checks: schema conformance + required fields
- Type/shape conformance + required-field presence; thresholds in `pack.yaml`.
- Depends on: T-021.

### T-023 Checks: null-rate
- Per-field null-rate thresholds, configurable.
- Depends on: T-021.

### T-024 Checks: value-range / format
- Range + format/referential sanity (dates, codes, non-negative amounts).
- Depends on: T-021.

### T-025 Checks: row-count delta anomaly
- Block/warn on drop-size delta vs. previous drop (Release-Analyzer style); thresholds configurable.
- Depends on: T-021.

### T-026 Fail-closed publish + quarantine
- Drop published (`checks_passed=true`, queryable) only if all blocking checks pass; failures quarantined, last-good untouched (test).
- Depends on: T-022, T-023, T-024, T-025.

### T-027 Alerting
- Failures alert to the log sink; optional Slack webhook via env.
- Depends on: T-026.

### T-028 Drift + provenance API
- Schema drift invalidates mapping cache + triggers re-map; value drift → `drift_events`; provenance API returns source/run/mapping-version/checks for a row.
- **M2.** Depends on: T-020, T-021.

---

## Epic F — Orchestration

### T-029 Dagster assets
- Assets fetch → extract → gate → store → publish with visible lineage.
- Depends on: T-026, T-028.

### T-030 Schedule + retries
- Schedule runs the flagship; retries with backoff on transient fetch/LLM errors.
- Depends on: T-029.

### T-031 Run lifecycle
- Runs marked `ok`/`degraded`/`failed`; degraded keeps previous published drop; statuses map to fetch/LLM/gate failures (test).
- **M3.** Depends on: T-030.

---

## Epic G — UI (high craft, HTMX + Jinja)

### T-032 Design system
- Design tokens (color scales, type scale, spacing, radius, shadow) as CSS vars; base stylesheet; light/dark; primitives (stack, grid, card, table, badge, button, tabs).
- HTMX + Jinja base; a `/styleguide` page renders every primitive. Restrained, dense, legible, WCAG AA. No gradient/emoji slop.
- Depends on: T-006.

### T-033 App shell
- Persistent nav + header; responsive; active-route states; persisted light/dark toggle.
- Depends on: T-032.

### T-034 Auth
- Token auth; login page; unauthenticated control/admin routes rejected; read-only explorer optionally public (documented).
- Depends on: T-033.

### T-035 Overview dashboard
- KPI tiles (freshness, gate pass rate, open drift, spend) + recent-activity feed; real empty/loading states.
- Depends on: T-033.

### T-036 Runs list + detail
- Paginated runs list with status; run detail with a stage timeline + Dagster links.
- Depends on: T-035, T-031.

### T-037 System logs stream
- Live log view (HTMX poll/SSE) with level + source filters.
- Depends on: T-033, T-004.

### T-038 Gate-failure browser
- For a failed run: which checks failed + exact offending rows, browsable.
- Depends on: T-036, T-026.

### T-039 Source management
- List sources; enable/disable; status/cadence at a glance.
- Depends on: T-035.

### T-040 Source detail
- Learned mapping/extraction plan, cadence, drop history, per-source quality trend.
- Depends on: T-039, T-028.

### T-041 Canonical explorer
- Filter/sort/paginate canonical records; provenance drawer per row.
- Depends on: T-035, T-028.

### T-042 Output views
- (a) value/price variation, (b) change-over-time, (c) data-quality scorecard — canonical/eval/drift-driven so they work for any Pack.
- Depends on: T-041.

### T-043 Cost readout
- Tokens per run/Pack; $0-local vs. would-be-Claude; note spend tracks schema changes not run count.
- Depends on: T-035, T-011.

### T-044 Add-a-source wizard + states
- Multi-step: upload sample / paste URL → LLM proposes schema + draft checks → review/tweak → save writes `packs/<name>/` and is loaded.
- Empty/loading/error states across the app; a11y + keyboard pass.
- **M4.** Depends on: T-039, T-019, T-021.

---

## Epic H — Genericness

### T-045 triage reference Pack (CFPB)
- Adapter (complaint narratives) + schema (category/severity/routing) + checks + one output view; **zero core changes** (acceptance test).
- Depends on: T-026.

### T-046 normalize reference Pack (USAspending)
- Adapter + canonical schema + checks; exercises mapping cache + schema-drift path.
- **M5.** Depends on: T-028.

---

## Epic I — Publishing & OSS polish

### T-047 Dataset publisher
- On a gate-passed drop, export canonical slice to a GitHub data repo + Hugging Face Datasets; idempotent; skipped for quarantined drops.
- Depends on: T-026.

### T-048 Test suite + CI
- Eval-check unit tests, adapter contract tests, one golden-file test per Pack, drift tests; GitHub Actions runs migrations + tests on PR.
- Depends on: T-045, T-046.

### T-049 README + tutorial + demo
- README (what/why, quick start, architecture diagram, trust-layer wedge); "write your own Pack" tutorial; demo GIF.
- Depends on: T-044, T-045.

### T-050 LICENSE + CONTRIBUTING + templates
- Permissive LICENSE; CONTRIBUTING; issue/PR templates; `packs/_template` cross-linked.
- **M6.** Depends on: T-049.
