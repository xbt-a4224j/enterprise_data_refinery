import httpx

from edr.packs.adapters import SocrataAdapter, build_adapter
from edr.packs.base import SourceSpec


def _spec():
    return SourceSpec(name="permits-sf", kind="socrata",
                      location="https://example.org/resource/x.json", options={"limit": 3})


def test_build_adapter_routes_socrata(tmp_path):
    assert isinstance(build_adapter(_spec(), tmp_path), SocrataAdapter)


def test_socrata_discovers_batch_and_renders_doc(tmp_path, monkeypatch):
    rows = [
        {"permit_number": "SF-1", "estimated_cost": "48500", "status": "issued",
         ":@computed_region_x": "noise"},
        {"permit_number": "SF-2", "estimated_cost": "1200", "status": "filed"},
    ]

    def fake_get(url, **kw):
        assert "$limit=3" in url
        return httpx.Response(200, json=rows, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    ad = SocrataAdapter(_spec(), tmp_path)
    refs = ad.discover()
    assert refs == ["0", "1"]
    doc = ad.fetch("0")
    assert "permit_number: SF-1" in doc.content
    assert ":@computed_region_x" not in doc.content  # noise fields dropped
    assert doc.meta["kind"] == "socrata"
