"""AgentContext.current_tool_call_id 필드 회귀 테스트 (TOOL-03 cache keying 지원)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.core.agent.config import AgentConfig
from app.core.agent.context import AgentContext


def _mk(tool_call_id: str | None = None) -> AgentContext:
    kwargs = dict(
        db_adapter=MagicMock(),
        llm_adapter=MagicMock(),
        db_name="test_db",
        user="alice",
        config=AgentConfig(),
    )
    if tool_call_id is not None:
        kwargs["current_tool_call_id"] = tool_call_id
    return AgentContext(**kwargs)


class ToolCallIdFieldTest(unittest.TestCase):
    def test_default_is_none(self) -> None:
        self.assertIsNone(_mk().current_tool_call_id)

    def test_constructor_override_sets_value(self) -> None:
        self.assertEqual(_mk("call_abc").current_tool_call_id, "call_abc")

    def test_post_construction_mutable(self) -> None:
        ctx = _mk()
        ctx.current_tool_call_id = "call_xyz"
        self.assertEqual(ctx.current_tool_call_id, "call_xyz")

    def test_instance_level_field(self) -> None:
        ctx1 = _mk("call_one")
        ctx2 = _mk("call_two")
        self.assertEqual(ctx1.current_tool_call_id, "call_one")
        self.assertEqual(ctx2.current_tool_call_id, "call_two")
        ctx1.current_tool_call_id = "mutated"
        self.assertEqual(ctx2.current_tool_call_id, "call_two")


if __name__ == "__main__":
    unittest.main()
