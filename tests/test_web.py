import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from edr.app import app
from edr.db import get_session
from edr.llm.fake import FakeProvider
from edr.models import Source
from edr.packs.loader import discover_packs
from edr.pipeline.run import ingest

ROOT = Path(__file__).resolve().parent.parent


def _parse(text):
    def find(*p):
        for pat in p:
            m = re.search(pat, text, re.I)
            if m:
                return m.group(1).strip()
        return None
    val = find(r"(?:Valuation|Job Value)[^$]*\$([\d,]+)")
    return {
        "permit_id": find(r"Permit No:\s*(\S+)", r"Permit ID:\s*(\S+)", r"No\.\s*(\S+)"),
        "valuation_usd": float(val.replace(",", "")) if val else None,
        "status": find(r"(?:Current Status|Status):\s*(.+)"),
    }


@pytest.fixture
def client(db_session):
    pack = discover_packs(ROOT / "packs")["extract"]
    src = Source(pack_name="extract", name="permits-demo")
    db_session.add(src)
    db_session.flush()
    ingest(db_session, pack, src, FakeProvider(responder=_parse), pack_dir=pack.pack_dir)
    db_session.commit()
    app.dependency_overrides[get_session] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_all_pages_render(client):
    for p in ["/", "/runs", "/gate", "/logs", "/sources", "/explore", "/outputs",
              "/cost", "/wizard", "/styleguide", "/login", "/health"]:
        assert client.get(p).status_code == 200, p


def test_overview_and_explorer_show_real_data(client):
    assert "Gate pass rate" in client.get("/").text
    assert "BLD-2026-00417" in client.get("/explore").text


def test_provenance_drawer(client):
    m = re.search(r"/explore/row/(\d+)", client.get("/explore").text)
    assert m
    assert "Checks passed" in client.get(f"/explore/row/{m.group(1)}").text


def test_control_route_requires_auth(client):
    # unauthenticated toggle -> redirect to login (303), not performed
    r = client.post("/sources/1/toggle", follow_redirects=False)
    assert r.status_code == 303 and "/login" in r.headers.get("location", "")
