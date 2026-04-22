"""TOOL-03 pivot_to_wide 단위 테스트: happy / pydantic / aggfunc='first' dedup / empty (TEST-01)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import pandas as pd
from pydantic import ValidationError

from app.core.agent.config import AgentConfig
from app.core.agent.context import AgentContext
from app.core.agent.tools._base import Tool
from app.core.agent.tools.pivot_to_wide import (
    PivotToWideArgs,
    pivot_to_wide_tool,
)


def _mk_ctx(df_to_return: pd.DataFrame, tool_call_id: str | None = None) -> AgentContext:
    db = MagicMock()
    db.run_query.return_value = df_to_return
    kwargs: dict = dict(
        db_adapter=db,
        llm_adapter=MagicMock(),
        db_name="unit_db",
        user="alice",
        config=AgentConfig(),
    )
    if tool_call_id is not None:
        kwargs["current_tool_call_id"] = tool_call_id
    return AgentContext(**kwargs)


_LONG_DF = pd.DataFrame(
    {
        "parameter": ["wb_enable", "wb_enable", "buffer", "buffer"],
        "PLATFORM_ID": ["A", "B", "A", "B"],
        "Result": [1, 0, 128, 64],
    }
)


class PivotHappyPathTest(unittest.TestCase):
    def test_pivots_and_caches(self) -> None:
        ctx = _mk_ctx(_LONG_DF, tool_call_id="call_pivot_1")
        result = pivot_to_wide_tool(ctx, PivotToWideArgs(category="§3", item="wb_enable"))
        self.assertEqual(result.df_ref, "call_pivot_1")
        cached = ctx.get_df("call_pivot_1")
        self.assertIsNotNone(cached)
        self.assertEqual(cached.shape, (2, 2))
        # verify SQL shape
        sql = ctx.db_adapter.run_query.call_args[0][0]
        self.assertIn("InfoCatergory = '§3'", sql)
        self.assertIn("Item = 'wb_enable'", sql)
        self.assertIn("LIMIT 200", sql)


class PivotAggfuncFirstDedupTest(unittest.TestCase):
    def test_duplicate_key_kept_first(self) -> None:
        long_with_dup = pd.DataFrame(
            {
                "parameter": ["wb_enable", "wb_enable", "wb_enable"],
                "PLATFORM_ID": ["A", "B", "A"],  # (wb_enable, A) appears twice
                "Result": [1, 0, 999],           # second A should be dropped
            }
        )
        ctx = _mk_ctx(long_with_dup, tool_call_id="call_dup")
        pivot_to_wide_tool(ctx, PivotToWideArgs(category="§3", item="wb_enable"))
        wide = ctx.get_df("call_dup")
        self.assertEqual(wide.loc["wb_enable", "A"], 1)  # FIRST, not 999


class PivotPydanticTest(unittest.TestCase):
    def test_missing_both(self) -> None:
        with self.assertRaises(ValidationError):
            PivotToWideArgs()  # type: ignore[call-arg]

    def test_missing_item(self) -> None:
        with self.assertRaises(ValidationError):
            PivotToWideArgs(category="§3")  # type: ignore[call-arg]


class PivotEmptyResultTest(unittest.TestCase):
    def test_no_rows_friendly_message_no_cache_write(self) -> None:
        empty = pd.DataFrame(columns=["parameter", "PLATFORM_ID", "Result"])
        ctx = _mk_ctx(empty, tool_call_id="call_empty")
        result = pivot_to_wide_tool(ctx, PivotToWideArgs(category="§3", item="missing"))
        self.assertIsNone(result.df_ref)
        self.assertTrue(result.content.startswith("No rows matched"))
        self.assertIsNone(ctx.get_df("call_empty"))


class PivotUuidFallbackTest(unittest.TestCase):
    def test_uuid_used_when_no_current_tool_call_id(self) -> None:
        ctx = _mk_ctx(_LONG_DF)  # current_tool_call_id defaults to None
        result = pivot_to_wide_tool(ctx, PivotToWideArgs(category="§3", item="wb_enable"))
        self.assertIsNotNone(result.df_ref)
        self.assertTrue(len(result.df_ref) > 0)
        self.assertIsNotNone(ctx.get_df(result.df_ref))


class PivotSqlEscapeTest(unittest.TestCase):
    def test_single_quote_escaped(self) -> None:
        ctx = _mk_ctx(_LONG_DF, tool_call_id="call_esc")
        pivot_to_wide_tool(ctx, PivotToWideArgs(category="O'Brien", item="wb_enable"))
        sql = ctx.db_adapter.run_query.call_args[0][0]
        self.assertIn("InfoCatergory = 'O''Brien'", sql)


class PivotProtocolTest(unittest.TestCase):
    def test_is_a_tool(self) -> None:
        self.assertIsInstance(pivot_to_wide_tool, Tool)


if __name__ == "__main__":
    unittest.main()
