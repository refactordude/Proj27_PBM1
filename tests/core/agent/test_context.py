"""AgentContext _df_cache 인스턴스별 독립성 검증 (SC2, AGENT-07)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import pandas as pd

from app.core.agent.config import AgentConfig
from app.core.agent.context import AgentContext


def _mk() -> AgentContext:
    return AgentContext(
        db_adapter=MagicMock(),
        llm_adapter=MagicMock(),
        db_name="test_db",
        user="alice",
        config=AgentConfig(),
    )


class AgentContextIsolationTest(unittest.TestCase):
    def test_df_cache_is_instance_level(self) -> None:
        ctx1 = _mk()
        ctx2 = _mk()
        ctx1.store_df("call_1", pd.DataFrame({"x": [1]}))
        self.assertIsNone(ctx2.get_df("call_1"))
        self.assertIsNot(ctx1._df_cache, ctx2._df_cache)

    def test_fresh_instance_has_empty_cache(self) -> None:
        ctx = _mk()
        self.assertEqual(ctx._df_cache, {})


class AgentContextCacheRoundTripTest(unittest.TestCase):
    def test_store_and_get_df(self) -> None:
        ctx = _mk()
        df = pd.DataFrame({"y": [42]})
        ctx.store_df("call_abc", df)
        self.assertIs(ctx.get_df("call_abc"), df)

    def test_get_missing_returns_none(self) -> None:
        ctx = _mk()
        self.assertIsNone(ctx.get_df("never_stored"))


if __name__ == "__main__":
    unittest.main()
