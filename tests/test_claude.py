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


def test_per_model_pricing_and_local_reference():
    from edr.llm.base import LLMResult

    haiku = LLMResult(data={}, tokens_in=1_000_000, tokens_out=1_000_000, model="claude-haiku-4-5")
    sonnet = LLMResult(data={}, tokens_in=1_000_000, tokens_out=1_000_000, model="claude-sonnet-5")
    local = LLMResult(data={}, tokens_in=1_000_000, tokens_out=1_000_000)  # no model
    assert round(haiku.would_be_claude_usd, 2) == 6.00     # $1 in + $5 out
    assert round(sonnet.would_be_claude_usd, 2) == 18.00   # $3 in + $15 out
    assert local.would_be_claude_usd == sonnet.would_be_claude_usd  # local uses Sonnet-5 reference
