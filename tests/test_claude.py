import httpx
import pytest

from edr.llm.claude import ClaudeProvider


def test_requires_key():
    with pytest.raises(ValueError):
        ClaudeProvider("")


def test_extract_with_mocked_api():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "sk-test"
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": '{"permit_id": "BLD-1"}'}],
                "usage": {"input_tokens": 120, "output_tokens": 8},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    prov = ClaudeProvider("sk-test", client=client)
    r = prov.extract(instructions="x", schema={"properties": {}}, content="doc")
    assert r.data == {"permit_id": "BLD-1"}
    assert r.tokens_in == 120 and r.tokens_out == 8 and r.would_be_claude_usd > 0
