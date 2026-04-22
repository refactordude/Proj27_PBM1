"""Ollama(로컬 LLM) 어댑터.

Ollama가 로컬에서 `ollama serve`로 떠 있을 때 http://localhost:11434 를 endpoint로 사용한다.
설정에서 endpoint와 모델명(예: "llama3.1:8b")만 바꾸면 동작한다.
"""
from __future__ import annotations

import json
from typing import Iterable

import requests

from app.adapters.llm.base import LLMAdapter, SQL_SYSTEM_PROMPT


class OllamaAdapter(LLMAdapter):
    def _endpoint(self) -> str:
        return (self.config.endpoint or "http://localhost:11434").rstrip("/")

    def _chat(self, messages: list[dict], *, stream: bool) -> Iterable[str] | str:
        url = f"{self._endpoint()}/api/chat"
        payload = {
            "model": self.config.model or "llama3.1",
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }
        if stream:
            resp = requests.post(url, json=payload, stream=True, timeout=120)
            resp.raise_for_status()
            return _iter_ollama_stream(resp)
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")

    def generate_sql(
        self,
        question: str,
        schema_summary: str,
        history: list[dict] | None = None,
    ) -> str:
        messages: list[dict] = [{"role": "system", "content": SQL_SYSTEM_PROMPT}]
        if schema_summary:
            messages.append(
                {"role": "system", "content": f"스키마:\n{schema_summary}"}
            )
        for turn in history or []:
            if turn.get("role") in {"user", "assistant"}:
                messages.append({"role": turn["role"], "content": turn.get("content", "")})
        messages.append({"role": "user", "content": question})
        return str(self._chat(messages, stream=False)).strip()

    def stream_text(self, prompt: str) -> Iterable[str]:
        messages = [{"role": "user", "content": prompt}]
        return _iter_ollama_stream_wrap(self._chat(messages, stream=True))


def _iter_ollama_stream(resp: requests.Response) -> Iterable[str]:
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        chunk = obj.get("message", {}).get("content")
        if chunk:
            yield chunk


def _iter_ollama_stream_wrap(iterable: Iterable[str] | str) -> Iterable[str]:
    if isinstance(iterable, str):
        yield iterable
        return
    yield from iterable
