"""_AGENT_TRACE_KEY + append/get helper behavior — HOME-04 저장 계약."""
from __future__ import annotations

import unittest

import streamlit as st

from app.core.session import (
    _AGENT_TRACE_KEY,
    _CHAT_HISTORY_KEY,
    _RECENT_QUERIES_KEY,
    _SELECTED_DB_KEY,
    _SELECTED_LLM_KEY,
    append_agent_trace,
    get_agent_trace,
)


class AgentTraceSessionHelpersTest(unittest.TestCase):
    def setUp(self) -> None:
        # 각 테스트마다 에이전트 트레이스 슬롯을 초기화 (chat_history도 정리).
        for key in (_AGENT_TRACE_KEY, _CHAT_HISTORY_KEY):
            if key in st.session_state:
                del st.session_state[key]

    def test_key_constant_is_locked_string(self) -> None:
        self.assertEqual(_AGENT_TRACE_KEY, "agent_trace_v1")

    def test_append_and_get_roundtrip(self) -> None:
        steps = [{"step": 1}, {"step": 2}]
        append_agent_trace(0, steps)
        self.assertEqual(get_agent_trace(0), [{"step": 1}, {"step": 2}])

    def test_get_missing_turn_returns_empty_list(self) -> None:
        self.assertEqual(get_agent_trace(999), [])

    def test_multiple_turns_independent(self) -> None:
        append_agent_trace(0, [{"a": 1}])
        append_agent_trace(1, [{"b": 2}])
        self.assertEqual(get_agent_trace(0), [{"a": 1}])
        self.assertEqual(get_agent_trace(1), [{"b": 2}])

    def test_append_copies_caller_list(self) -> None:
        original = [{"step": 1}]
        append_agent_trace(0, original)
        original.append({"step": 2})  # 외부 변이
        stored = get_agent_trace(0)
        self.assertEqual(stored, [{"step": 1}])  # 내부 복사본은 영향 없음

    def test_agent_trace_key_does_not_collide(self) -> None:
        other_keys = {
            _CHAT_HISTORY_KEY,
            _RECENT_QUERIES_KEY,
            _SELECTED_DB_KEY,
            _SELECTED_LLM_KEY,
        }
        self.assertNotIn(_AGENT_TRACE_KEY, other_keys)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
