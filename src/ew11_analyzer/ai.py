"""Send analysis reports to an AI API.

Two provider modes:

- ``openai``: any OpenAI-compatible ``/chat/completions`` endpoint — works with
  OpenAI, OpenRouter, Ollama (``http://localhost:11434/v1``), LM Studio, etc.
- ``anthropic``: Anthropic ``/v1/messages`` endpoint.

The API key stays on this machine (local config file); nothing is sent
anywhere unless the user clicks "AI에게 보내기".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.openai.com/v1"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

SYSTEM_PROMPT = (
    "당신은 RS485 홈네트워크/월패드 프로토콜 리버스 엔지니어링 전문가입니다. "
    "사용자가 제공하는 패킷 분석 리포트를 바탕으로 프로토콜 구조, 각 패킷의 의미, "
    "체크섬, 명령 바이트를 추정하고 검증 실험을 제안합니다. "
    "확실하지 않은 내용은 반드시 '추정'이라고 표시하고, 근거(바이트 위치, 샘플)를 함께 제시하세요. "
    "답변은 한국어로 작성합니다."
)


@dataclass
class AiConfig:
    provider: str = "openai"  # 'openai' (compatible) | 'anthropic'
    base_url: str = DEFAULT_BASE_URL
    api_key: str = ""
    model: str = "gpt-4o-mini"
    max_tokens: int = 4096

    def sanitized(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "api_key": ("***" + self.api_key[-4:]) if self.api_key else "",
            "has_key": bool(self.api_key),
            "model": self.model,
            "max_tokens": self.max_tokens,
        }


def _extract_openai(data: dict[str, Any]) -> str:
    try:
        return str(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(f"AI 응답 파싱 실패: {data!r}") from e


def _extract_anthropic(data: dict[str, Any]) -> str:
    try:
        parts = [b["text"] for b in data["content"] if b.get("type") == "text"]
        return "".join(parts)
    except (KeyError, TypeError) as e:
        raise ValueError(f"Anthropic 응답 파싱 실패: {data!r}") from e


async def analyze_report(report_md: str, cfg: AiConfig, client: httpx.AsyncClient | None = None) -> str:
    if not cfg.api_key:
        raise ValueError("API 키가 설정되지 않았습니다. 설정 탭에서 입력하세요.")

    own_client = client is None
    http = client or httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=15.0))
    try:
        if cfg.provider == "anthropic":
            resp = await http.post(
                ANTHROPIC_URL,
                headers={
                    "x-api-key": cfg.api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": cfg.model or "claude-sonnet-4-5",
                    "max_tokens": cfg.max_tokens,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": report_md}],
                },
            )
            resp.raise_for_status()
            return _extract_anthropic(resp.json())

        base = cfg.base_url.rstrip("/")
        resp = await http.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {cfg.api_key}"},
            json={
                "model": cfg.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": report_md},
                ],
                "max_tokens": cfg.max_tokens,
            },
        )
        resp.raise_for_status()
        return _extract_openai(resp.json())
    finally:
        if own_client:
            await http.aclose()
