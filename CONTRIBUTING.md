# Contributing

## Dev setup
```bash
make dev        # uv sync
docker compose up -d db
make migrate    # alembic upgrade head
make test       # pytest
make lint       # ruff
```

## Writing a Pack
A Pack is one document domain and needs **zero core changes**. Copy the template:
```bash
cp -r packs/_template packs/<your-name>
```
Edit `pack.yaml` (sources, task type, instructions, check thresholds), `schema.py`
(your canonical `BaseModel`), and `checks.py` (a `CHECKS` list). `docker compose up`
auto-discovers it. Or use the **Add a source** wizard in the UI.

## Bar for merge
- `make test` and `make lint` green.
- New checks are unit-tested (feed known-bad input, assert the gate blocks it).
- Each Pack ships at least one golden-file test.
