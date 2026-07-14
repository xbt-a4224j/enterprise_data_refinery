from fastapi.testclient import TestClient

from edr.app import app
from edr.db import get_session
from edr.packs.loader import load_pack
from edr.web.wizard import propose_fields, write_pack

SAMPLE = "Permit No: BLD-1\nStatus: Issued\nValuation: $10\n"


def test_propose_fields_heuristic():
    fields = propose_fields(None, SAMPLE)
    names = {f["name"] for f in fields}
    assert "permit_no" in names and "status" in names


def test_write_pack_is_loadable(tmp_path):
    d = write_pack("Invoices", propose_fields(None, SAMPLE), SAMPLE, base_dir=tmp_path)
    pack = load_pack(d)
    assert pack.config.name == "invoices"
    assert "status" in pack.schema_model.model_fields


def test_wizard_propose_requires_auth(db_session):
    app.dependency_overrides[get_session] = lambda: db_session
    try:
        c = TestClient(app)
        # no auth -> redirected to login
        r = c.post("/wizard/propose", data={"name": "x", "sample": SAMPLE},
                   follow_redirects=False)
        assert r.status_code == 303
        # authed -> proposal rendered
        c.cookies.set("edr_token", "change-me")
        r2 = c.post("/wizard/propose", data={"name": "invoices", "sample": SAMPLE})
        assert r2.status_code == 200 and "Proposed schema" in r2.text
    finally:
        app.dependency_overrides.clear()
