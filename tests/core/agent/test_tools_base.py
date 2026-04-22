"""Tool Protocol 구조적 타입 및 ToolResult 모델 검증 (SC3)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pydantic import BaseModel

from app.core.agent.config import AgentConfig
from app.core.agent.context import AgentContext
from app.core.agent.tools._base import Tool, ToolResult


class _ToyArgs(BaseModel):
    message: str


class _ToyTool:
    name = "toy"
    args_model = _ToyArgs

    def __call__(self, ctx: AgentContext, args: BaseModel) -> ToolResult:
        assert isinstance(args, _ToyArgs)
        return ToolResult(content=f"echo: {args.message}")


class ToolProtocolTest(unittest.TestCase):
    def test_toy_tool_satisfies_protocol(self) -> None:
        self.assertIsInstance(_ToyTool(), Tool)

    def test_missing_name_fails_protocol(self) -> None:
        class _NoName:
            args_model = _ToyArgs

            def __call__(self, ctx, args):  # pragma: no cover
                return ToolResult(content="x")

        self.assertNotIsInstance(_NoName(), Tool)

    def test_missing_args_model_fails_protocol(self) -> None:
        class _NoArgsModel:
            name = "bad"

            def __call__(self, ctx, args):  # pragma: no cover
                return ToolResult(content="x")

        self.assertNotIsInstance(_NoArgsModel(), Tool)


class ToolResultTest(unittest.TestCase):
    def test_defaults(self) -> None:
        r = ToolResult(content="hello")
        self.assertEqual(r.content, "hello")
        self.assertIsNone(r.df_ref)
        self.assertIsNone(r.chart)
        dumped = r.model_dump()
        self.assertEqual(dumped["content"], "hello")

    def test_full_payload(self) -> None:
        r = ToolResult(content="42 rows", df_ref="call_xyz", chart=None)
        self.assertEqual(r.df_ref, "call_xyz")

    def test_arbitrary_chart_allowed(self) -> None:
        """ConfigDict(arbitrary_types_allowed=True) permits non-Pydantic types."""
        sentinel = object()
        r = ToolResult(content="chart", chart=sentinel)
        self.assertIs(r.chart, sentinel)


class ToolCallIntegrationTest(unittest.TestCase):
    def test_tool_call_returns_tool_result(self) -> None:
        ctx = AgentContext(
            db_adapter=MagicMock(),
            llm_adapter=MagicMock(),
            db_name="db",
            user="u",
            config=AgentConfig(),
        )
        tool = _ToyTool()
        result = tool(ctx, _ToyArgs(message="hi"))
        self.assertIsInstance(result, ToolResult)
        self.assertEqual(result.content, "echo: hi")


if __name__ == "__main__":
    unittest.main()
