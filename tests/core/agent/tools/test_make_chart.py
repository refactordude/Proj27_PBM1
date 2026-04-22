"""TOOL-06 make_chart 단위 테스트: 4 chart_type happy path + pydantic + missing-ref (TEST-01)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import pandas as pd
import plotly.graph_objects as go
from pydantic import ValidationError

from app.core.agent.config import AgentConfig
from app.core.agent.context import AgentContext
from app.core.agent.tools._base import Tool
from app.core.agent.tools.make_chart import (
    MakeChartArgs,
    make_chart_tool,
)


def _mk_ctx() -> AgentContext:
    return AgentContext(
        db_adapter=MagicMock(),
        llm_adapter=MagicMock(),
        db_name="unit_db",
        user="alice",
        config=AgentConfig(),
    )


def _fixture_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "device": ["A", "B", "C"],
            "capacity_gb": [128, 256, 512],
            "brand": ["X", "Y", "X"],
        }
    )


def _fixture_heatmap_df() -> pd.DataFrame:
    return pd.DataFrame(
        [[1, 2], [3, 4]],
        index=["A", "B"],
        columns=["metric1", "metric2"],
    )


class MakeChartHappyPathTest(unittest.TestCase):
    def _ctx_with(self, df: pd.DataFrame, key: str = "df1") -> AgentContext:
        ctx = _mk_ctx()
        ctx._df_cache[key] = df
        return ctx

    def test_bar_chart(self) -> None:
        ctx = self._ctx_with(_fixture_df())
        args = MakeChartArgs(
            chart_type="bar",
            data_ref="df1",
            x="device",
            y="capacity_gb",
            title="Cap",
        )
        result = make_chart_tool(ctx, args)
        self.assertIsNotNone(result.chart)
        self.assertIsInstance(result.chart, go.Figure)
        self.assertIn("bar", result.content)

    def test_line_chart(self) -> None:
        ctx = self._ctx_with(_fixture_df())
        args = MakeChartArgs(
            chart_type="line",
            data_ref="df1",
            x="device",
            y="capacity_gb",
        )
        result = make_chart_tool(ctx, args)
        self.assertIsInstance(result.chart, go.Figure)
        self.assertIn("line", result.content)

    def test_scatter_chart(self) -> None:
        ctx = self._ctx_with(_fixture_df())
        args = MakeChartArgs(
            chart_type="scatter",
            data_ref="df1",
            x="device",
            y="capacity_gb",
            color="brand",
        )
        result = make_chart_tool(ctx, args)
        self.assertIsInstance(result.chart, go.Figure)
        self.assertIn("scatter", result.content)

    def test_heatmap_chart(self) -> None:
        ctx = self._ctx_with(_fixture_heatmap_df())
        args = MakeChartArgs(chart_type="heatmap", data_ref="df1", title="Heat")
        result = make_chart_tool(ctx, args)
        self.assertIsInstance(result.chart, go.Figure)
        self.assertIn("heatmap", result.content)

    def test_tool_satisfies_protocol(self) -> None:
        self.assertIsInstance(make_chart_tool, Tool)
        self.assertEqual(make_chart_tool.name, "make_chart")


class MakeChartArgValidationTest(unittest.TestCase):
    def test_invalid_chart_type_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            MakeChartArgs(chart_type="pie", data_ref="x")  # type: ignore[arg-type]

    def test_missing_data_ref_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            MakeChartArgs(chart_type="bar")  # type: ignore[call-arg]


class MakeChartMissingRefTest(unittest.TestCase):
    def test_missing_data_ref_returns_error(self) -> None:
        ctx = _mk_ctx()  # empty _df_cache
        args = MakeChartArgs(
            chart_type="bar",
            data_ref="nonexistent",
            x="device",
            y="capacity_gb",
        )
        result = make_chart_tool(ctx, args)
        self.assertIsNone(result.chart)
        self.assertTrue(result.content.startswith("make_chart error: data_ref"))


if __name__ == "__main__":
    unittest.main()
