"""OpenAI LLM 어댑터.

openai>=1.0 SDK의 chat.completions API 사용.
API key는 설정에 직접 입력하거나, 비워두면 OPENAI_API_KEY 환경변수를 사용한다.
30초 요청 타임아웃(httpx.Timeout)으로 무한 대기를 방지한다 (AGENT-08).
"""
from __future__ import annotations

import os
from typing import Iterable

import httpx
from openai import OpenAI

from app.adapters.llm.base import LLMAdapter, SQL_SYSTEM_PROMPT

_REQUEST_TIMEOUT = httpx.Timeout(30.0)


class OpenAIAdapter(LLMAdapter):
    def _client(self) -> OpenAI:
        api_key = self.config.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OpenAI API key가 설정되지 않았습니다. "
                "Settings에서 입력하거나 OPENAI_API_KEY 환경변수를 설정하세요."
            )
        base_url = self.config.endpoint or None
        return OpenAI(api_key=api_key, base_url=base_url)

    def _extra_headers(self) -> dict | None:
        return self.config.headers if self.config.headers else None

    def generate_sql(
        self,
        question: str,
        schema_summary: str,
        history: list[dict] | None = None,
    ) -> str:
        client = self._client()
        messages: list[dict] = [{"role": "system", "content": SQL_SYSTEM_PROMPT}]
        if schema_summary:
            messages.append(
                {
                    "role": "system",
                    "content": f"아래는 사용 가능한 테이블 스키마 요약입니다:\n{schema_summary}",
                }
            )
        for turn in history or []:
            if turn.get("role") in {"user", "assistant"}:
                messages.append({"role": turn["role"], "content": turn.get("content", "")})
        messages.append({"role": "user", "content": question})

        resp = client.chat.completions.create(
            model=self.config.model or "gpt-4o-mini",
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            extra_headers=self._extra_headers(),
            timeout=_REQUEST_TIMEOUT,
        )
        return (resp.choices[0].message.content or "").strip()

    def stream_text(self, prompt: str) -> Iterable[str]:
        client = self._client()
        stream = client.chat.completions.create(
            model=self.config.model or "gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=True,
            extra_headers=self._extra_headers(),
            timeout=_REQUEST_TIMEOUT,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
