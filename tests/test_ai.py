from __future__ import annotations

import json

import httpx
import pytest

from ew11_analyzer.ai import AiConfig, analyze_report


def _openai_ok(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    assert body["model"] == "test-model"
    assert body["messages"][1]["content"].startswith("# AI")
    assert request.headers["Authorization"] == "Bearer sk-test"
    return httpx.Response(200, json={"choices": [{"message": {"content": "분석 결과입니다"}}]})


def _anthropic_ok(request: httpx.Request) -> httpx.Response:
    assert request.headers["x-api-key"] == "sk-ant-test"
    assert request.headers["anthropic-version"] == "2023-06-01"
    return httpx.Response(200, json={"content": [{"type": "text", "text": "클로드 답변"}]})


async def test_openai_compatible():
    cfg = AiConfig(
        provider="openai", base_url="https://api.openai.com/v1", api_key="sk-test", model="test-model"
    )
    transport = httpx.MockTransport(_openai_ok)
    async with httpx.AsyncClient(transport=transport) as client:
        out = await analyze_report("# AI 분석 요청\n...", cfg, client=client)
    assert out == "분석 결과입니다"


async def test_anthropic():
    cfg = AiConfig(provider="anthropic", api_key="sk-ant-test", model="claude-sonnet-4-5")
    transport = httpx.MockTransport(_anthropic_ok)
    async with httpx.AsyncClient(transport=transport) as client:
        out = await analyze_report("report", cfg, client=client)
    assert out == "클로드 답변"


async def test_missing_key():
    with pytest.raises(ValueError):
        await analyze_report("x", AiConfig(api_key=""))


async def test_http_error_propagates():
    def _fail(request):
        return httpx.Response(401, json={"error": "unauthorized"})

    cfg = AiConfig(api_key="bad", base_url="https://x.example/v1")
    async with httpx.AsyncClient(transport=httpx.MockTransport(_fail)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await analyze_report("x", cfg, client=client)


def test_sanitized_masks_key():
    cfg = AiConfig(api_key="sk-secret1234")
    s = cfg.sanitized()
    assert s["api_key"].endswith("1234")
    assert "secret" not in s["api_key"]
