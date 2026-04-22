"""openai_adapter.py chat.completions.create 타임아웃 검증 (SC4, AGENT-08)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import httpx

from app.adapters.llm.openai_adapter import OpenAIAdapter, _REQUEST_TIMEOUT
from app.core.config import LLMConfig


def _mk_adapter() -> OpenAIAdapter:
    cfg = LLMConfig(
        name="test_openai",
        type="openai",
        model="gpt-4o-mini",
        api_key="sk-test",
    )
    return OpenAIAdapter(cfg)


class RequestTimeoutConstantTest(unittest.TestCase):
    def test_timeout_is_httpx_timeout_30s(self) -> None:
        self.assertIsInstance(_REQUEST_TIMEOUT, httpx.Timeout)
        # httpx.Timeout(30.0) with a single positional sets ALL phases to 30.0
        self.assertEqual(_REQUEST_TIMEOUT.read, 30.0)
        self.assertEqual(_REQUEST_TIMEOUT.connect, 30.0)
        self.assertEqual(_REQUEST_TIMEOUT.write, 30.0)
        self.assertEqual(_REQUEST_TIMEOUT.pool, 30.0)


class GenerateSqlTimeoutTest(unittest.TestCase):
    def test_generate_sql_passes_timeout(self) -> None:
        adapter = _mk_adapter()
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="SELECT 1"))]
        )
        with patch.object(adapter, "_client", return_value=fake_client):
            adapter.generate_sql(question="q", schema_summary="")
        kwargs = fake_client.chat.completions.create.call_args.kwargs
        self.assertIn("timeout", kwargs)
        self.assertIs(kwargs["timeout"], _REQUEST_TIMEOUT)


class StreamTextTimeoutTest(unittest.TestCase):
    def test_stream_text_passes_timeout_and_stream_flag(self) -> None:
        adapter = _mk_adapter()
        fake_client = MagicMock()
        # stream_text iterates the return — give it an empty iterator
        fake_client.chat.completions.create.return_value = iter([])
        with patch.object(adapter, "_client", return_value=fake_client):
            list(adapter.stream_text("prompt"))
        kwargs = fake_client.chat.completions.create.call_args.kwargs
        self.assertIn("timeout", kwargs)
        self.assertIs(kwargs["timeout"], _REQUEST_TIMEOUT)
        self.assertTrue(kwargs.get("stream") is True)


if __name__ == "__main__":
    unittest.main()
