"""run_agent_turn 통합 테스트 — mocked OpenAI client로 루프 제어 의미를 검증.

SC1: test_react_loop_run_sql_then_answer (TEST-02)
SC2: test_forced_finalization_on_budget_exhaustion (TEST-03)
SC3: test_parallel_tool_calls_false_on_every_create
SC4: test_streamlit_agnostic (grep + sys.modules check)
SC5: test_max_context_tokens_triggers_finalization
AGENT-07: test_stateless_per_turn — 턴 간 _df_cache 공유 없음
TEST-05 규율: 모델이 내뱉은 SQL 문자열 자체는 절대 assert하지 않는다 — 호출 순서/kwargs/step 시퀀스만 검증.
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

from app.core.agent.config import AgentConfig
from app.core.agent.context import AgentContext
from app.core.agent.loop import (
    AgentStep,
    _build_openai_tools,
    _build_system_prompt,
    run_agent_turn,
)
from app.core.agent.tools._base import ToolResult
from app.core.agent.tools.run_sql import RunSqlArgs


def _make_tool_call_response(
    *,
    tool_name: str,
    arguments: str,
    call_id: str = "call_x",
    prompt_tokens: int = 100,
    completion_tokens: int = 20,
) -> MagicMock:
    """tool_calls=[1개]을 가진 OpenAI ChatCompletion 응답 모형."""
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = tool_name
    tc.function.arguments = arguments

    msg = MagicMock()
    msg.content = None
    msg.tool_calls = [tc]

    choice = MagicMock()
    choice.message = msg

    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = MagicMock(
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
    )
    return resp


def _make_final_answer_response(
    text: str,
    *,
    prompt_tokens: int = 50,
    completion_tokens: int = 15,
) -> MagicMock:
    """tool_calls=None인 최종 답변 응답 모형."""
    msg = MagicMock()
    msg.content = text
    msg.tool_calls = None

    choice = MagicMock()
    choice.message = msg

    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = MagicMock(
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
    )
    return resp


def _make_ctx(
    *,
    max_steps: int = 5,
    timeout_s: int = 30,
    max_context_tokens: int = 30_000,
) -> tuple[AgentContext, MagicMock]:
    """AgentContext를 MagicMock llm_adapter._client()와 함께 생성."""
    cfg = AgentConfig(
        max_steps=max_steps,
        timeout_s=timeout_s,
        max_context_tokens=max_context_tokens,
    )
    fake_client = MagicMock()
    fake_llm_adapter = MagicMock()
    fake_llm_adapter._client.return_value = fake_client
    # _resolve_model falls back to the adapter's config.model when AgentConfig
    # has no override. Set a concrete string so log_llm(model=...) stays JSON
    # serializable and the loop mirrors real resolution behavior.
    fake_llm_adapter.config.model = "test-model"
    fake_db_adapter = MagicMock()

    ctx = AgentContext(
        db_adapter=fake_db_adapter,
        llm_adapter=fake_llm_adapter,
        db_name="test_db",
        user="test_user",
        config=cfg,
    )
    return ctx, fake_client


def _make_fake_run_sql(*, content: str = "Rows: 1\n|count|\n|7|") -> MagicMock:
    """TOOL_REGISTRY['run_sql']을 대체하는 MagicMock.

    - args_model은 실제 RunSqlArgs이므로 model_validate_json이 정상 동작한다.
    - 호출 시 ToolResult(content=...)를 반환하도록 설정.
    """
    fake = MagicMock(return_value=ToolResult(content=content))
    fake.name = "run_sql"
    fake.args_model = RunSqlArgs
    return fake


class ReactLoopRunSqlThenAnswerTest(unittest.TestCase):
    """2-step loop: run_sql → text final answer. create() called exactly twice."""

    def test_react_loop_run_sql_then_answer(self) -> None:
        ctx, fake_client = _make_ctx()

        # Step 0: 모델이 run_sql 호출. Step 1: 모델이 최종 답변.
        tool_call_resp = _make_tool_call_response(
            tool_name="run_sql",
            arguments='{"sql": "SELECT 1"}',
            call_id="call_1",
        )
        final_resp = _make_final_answer_response("The device count is 7.")
        fake_client.chat.completions.create.side_effect = [tool_call_resp, final_resp]

        fake_run_sql = _make_fake_run_sql(content="Rows: 1\n|count|\n|7|")

        with patch.dict(
            "app.core.agent.loop.TOOL_REGISTRY",
            {"run_sql": fake_run_sql},
            clear=False,
        ):
            steps = list(run_agent_turn("How many devices?", ctx))

        # SC1: create() 정확히 2회 호출.
        self.assertEqual(fake_client.chat.completions.create.call_count, 2)

        # AgentStep 시퀀스: tool_call, tool_result, final_answer.
        step_types = [s.step_type for s in steps]
        self.assertEqual(
            step_types, ["tool_call", "tool_result", "final_answer"]
        )

        # tool_call / tool_result 둘 다 tool_name == "run_sql".
        self.assertEqual(steps[0].tool_name, "run_sql")
        self.assertEqual(steps[1].tool_name, "run_sql")

        # TEST-05 규율: 디스패치된 도구와 sql 타입만 검증, SQL 문자열 내용은 검증하지 않는다.
        self.assertIsInstance(steps[0].sql, str)

        # 최종 답변 내용.
        self.assertEqual(steps[-1].step_type, "final_answer")
        self.assertEqual(steps[-1].content, "The device count is 7.")
        self.assertFalse(steps[-1].budget_exhausted)

        # 모든 step은 AgentStep 타입이어야 한다 (제너레이터 규약).
        for s in steps:
            self.assertIsInstance(s, AgentStep)


class ForcedFinalizationOnBudgetExhaustionTest(unittest.TestCase):
    """5 tool-call 응답 연속 → 6번째 create()가 tool_choice='none'으로 강제 종료.

    yield된 최종 step은 budget_exhausted=True여야 한다 (AGENT-04).
    """

    def test_forced_finalization_on_budget_exhaustion(self) -> None:
        ctx, fake_client = _make_ctx(max_steps=5)

        # 5회 연속 tool_call 응답. 정상 경로에선 "final answer"가 나오지 않는다.
        # 6번째 create()가 강제 종료 호출.
        tool_resps = [
            _make_tool_call_response(
                tool_name="run_sql",
                arguments='{"sql": "SELECT 1"}',
                call_id=f"call_{i}",
            )
            for i in range(5)
        ]
        forced_resp = _make_final_answer_response("Stopped after 5 steps.")
        fake_client.chat.completions.create.side_effect = tool_resps + [forced_resp]

        fake_run_sql = _make_fake_run_sql(content="Rows: 0")

        with patch.dict(
            "app.core.agent.loop.TOOL_REGISTRY",
            {"run_sql": fake_run_sql},
            clear=False,
        ):
            steps = list(run_agent_turn("q?", ctx))

        # 5 tool-call 응답 + 1 강제 종료 = 6회 create() 호출.
        self.assertEqual(fake_client.chat.completions.create.call_count, 6)

        # 마지막 step은 final_answer + budget_exhausted=True (AGENT-04).
        self.assertEqual(steps[-1].step_type, "final_answer")
        self.assertTrue(steps[-1].budget_exhausted)
        self.assertEqual(steps[-1].content, "Stopped after 5 steps.")

        # 6번째 create() 호출은 tool_choice="none"으로 발행되어야 한다.
        final_call_kwargs = fake_client.chat.completions.create.call_args_list[-1].kwargs
        self.assertEqual(final_call_kwargs["tool_choice"], "none")


class FirstCreateFailureReturnsFinalAnswerTest(unittest.TestCase):
    """첫 create() 호출이 예외를 던지면 루프는 단일 final_answer로 조기 종료한다.

    WR-03 regression guard: 루프 레벨 create() 실패는
    - step_type == "final_answer"
    - error 필드가 원본 예외 메시지로 채워짐
    - budget_exhausted == True (Phase 4 UI 조기-종료 분기용)
    - content에 "[loop error: ...]" 문자열 포함
    를 만족해야 한다. 강제 종료 경로(_forced_finalization)는 호출되지 않는다.
    """

    def test_first_create_failure_yields_single_error_final_answer(self) -> None:
        ctx, fake_client = _make_ctx()

        # 첫 create()가 네트워크 에러를 던진다. 두 번째 응답은 준비하지 않는다
        # (강제 종료 경로로 빠지지 않는지 create.call_count로 검증).
        error_message = "RateLimitError: 429"
        fake_client.chat.completions.create.side_effect = RuntimeError(error_message)

        fake_run_sql = _make_fake_run_sql(content="unused")

        with patch.dict(
            "app.core.agent.loop.TOOL_REGISTRY",
            {"run_sql": fake_run_sql},
            clear=False,
        ):
            steps = list(run_agent_turn("q?", ctx))

        # 정확히 1개의 AgentStep만 yield되어야 한다.
        self.assertEqual(len(steps), 1)
        step = steps[0]

        # final_answer + error 필드 채워짐 + budget_exhausted=True.
        self.assertEqual(step.step_type, "final_answer")
        self.assertIsNotNone(step.error)
        assert step.error is not None  # narrow for mypy-ish
        self.assertIn(error_message, step.error)
        self.assertTrue(step.budget_exhausted)

        # content 포맷 검증 (Phase 4 UI가 그대로 보여줄 문자열).
        self.assertIn("[loop error:", step.content)
        self.assertIn(error_message, step.content)

        # create()는 정확히 1회만 호출됨 — 강제 종료 경로로 빠지지 않는다.
        self.assertEqual(fake_client.chat.completions.create.call_count, 1)


class ParallelToolCallsFalseEveryCreateTest(unittest.TestCase):
    """parallel_tool_calls=False는 모든 create() 호출에 (main + forced) 반드시 포함."""

    def test_every_create_call_has_parallel_tool_calls_false(self) -> None:
        ctx, fake_client = _make_ctx(max_steps=3)

        tool_resp_1 = _make_tool_call_response(
            tool_name="run_sql",
            arguments='{"sql": "SELECT 1"}',
            call_id="call_a",
        )
        tool_resp_2 = _make_tool_call_response(
            tool_name="run_sql",
            arguments='{"sql": "SELECT 1"}',
            call_id="call_b",
        )
        final_resp = _make_final_answer_response("done")
        fake_client.chat.completions.create.side_effect = [
            tool_resp_1,
            tool_resp_2,
            final_resp,
        ]

        fake_run_sql = _make_fake_run_sql(content="ok")

        with patch.dict(
            "app.core.agent.loop.TOOL_REGISTRY",
            {"run_sql": fake_run_sql},
            clear=False,
        ):
            list(run_agent_turn("q?", ctx))

        # 모든 create() 호출에 parallel_tool_calls=False + timeout 키워드 존재.
        calls = fake_client.chat.completions.create.call_args_list
        self.assertEqual(len(calls), 3)
        for i, call in enumerate(calls):
            self.assertIn(
                "parallel_tool_calls", call.kwargs, f"call {i} missing kwarg"
            )
            self.assertIs(
                call.kwargs["parallel_tool_calls"],
                False,
                f"call {i} parallel_tool_calls != False",
            )
            # AGENT-08 연속성: timeout 키워드도 모든 호출에 존재.
            self.assertIn("timeout", call.kwargs, f"call {i} missing timeout kwarg")


class MaxContextTokensTriggersFinalizationTest(unittest.TestCase):
    """max_context_tokens를 초과하는 tool_result가 강제 종료를 트리거한다 (SC5 / AGENT-06).

    char/4 휴리스틱 + usage 토큰 합산이 cap을 넘으면 다음 턴 시작 전에
    tool_choice='none' 경로가 발동한다.
    """

    def test_oversized_tool_result_triggers_forced_finalization(self) -> None:
        # AgentConfig.max_context_tokens는 ge=1000 바운드를 가지므로 최솟값 1000을 사용.
        # 5000자 tool content (~1250 tokens) + usage 70 = 1320 tokens ≫ 1000 cap.
        ctx, fake_client = _make_ctx(max_steps=10, max_context_tokens=1000)

        tool_resp = _make_tool_call_response(
            tool_name="run_sql",
            arguments='{"sql": "SELECT 1"}',
            call_id="call_big",
            # usage 토큰도 조금 채워 넣어 경계를 확실히 넘긴다.
            prompt_tokens=60,
            completion_tokens=10,
        )
        forced_resp = _make_final_answer_response("Stopped: context too large.")
        # 1회 tool 호출 후 강제 종료: 두 번째 create()가 tool_choice="none"이어야 한다.
        fake_client.chat.completions.create.side_effect = [tool_resp, forced_resp]

        # 5000자 payload → char/4 heuristic으로 1250 tokens ≫ 1000 cap.
        big_payload = "x" * 5000
        fake_run_sql = _make_fake_run_sql(content=big_payload)

        with patch.dict(
            "app.core.agent.loop.TOOL_REGISTRY",
            {"run_sql": fake_run_sql},
            clear=False,
        ):
            steps = list(run_agent_turn("q?", ctx))

        # 최종 step은 final_answer + budget_exhausted=True.
        self.assertEqual(steps[-1].step_type, "final_answer")
        self.assertTrue(steps[-1].budget_exhausted)

        # 두 번째 create() 호출은 강제 종료 호출: tool_choice="none".
        last_call_kwargs = fake_client.chat.completions.create.call_args_list[-1].kwargs
        self.assertEqual(last_call_kwargs["tool_choice"], "none")

        # create()는 정확히 2회만 호출됨 — max_steps=10 예산을 전부 소진하지 않는다.
        self.assertEqual(fake_client.chat.completions.create.call_count, 2)


class StreamlitAgnosticTest(unittest.TestCase):
    """loop 모듈은 streamlit 의존 없이 import되고 실행 가능해야 한다 (SC4)."""

    def test_loop_module_does_not_import_streamlit(self) -> None:
        # 소스 파일에 streamlit import 구문이 0건이어야 한다 (정적 검사).
        import pathlib

        loop_path = pathlib.Path("app/core/agent/loop.py")
        self.assertTrue(loop_path.exists())
        content = loop_path.read_text(encoding="utf-8")
        self.assertNotIn("import streamlit", content)
        self.assertNotIn("from streamlit", content)

    def test_run_agent_turn_runs_without_streamlit_in_sys_modules(self) -> None:
        # streamlit을 sys.modules에서 제거한 뒤 루프를 실행 → streamlit이 다시
        # import되지 않는지 검증. (다른 테스트가 streamlit을 이미 로드했더라도
        # 테스트 종료 시 원상복구.)
        streamlit_saved = sys.modules.pop("streamlit", None)
        try:
            ctx, fake_client = _make_ctx()
            fake_client.chat.completions.create.side_effect = [
                _make_final_answer_response("hello")
            ]
            steps = list(run_agent_turn("hi", ctx))
            self.assertEqual(len(steps), 1)
            self.assertEqual(steps[0].step_type, "final_answer")
            self.assertEqual(steps[0].content, "hello")
            # 루프 실행 후에도 streamlit이 sys.modules에 없어야 한다.
            self.assertNotIn("streamlit", sys.modules)
        finally:
            if streamlit_saved is not None:
                sys.modules["streamlit"] = streamlit_saved


class StatelessPerTurnTest(unittest.TestCase):
    """두 번의 연속 run_agent_turn 호출이 독립 AgentContext를 사용해야 한다 (AGENT-07).

    _df_cache 딕셔너리는 턴 간 공유되지 않아야 한다.
    """

    def test_fresh_context_per_turn_distinct_df_caches(self) -> None:
        ctx1, fake_client1 = _make_ctx()
        ctx2, fake_client2 = _make_ctx()

        fake_client1.chat.completions.create.side_effect = [
            _make_final_answer_response("turn 1 done")
        ]
        fake_client2.chat.completions.create.side_effect = [
            _make_final_answer_response("turn 2 done")
        ]

        # 이전 턴의 _df_cache를 시뮬레이트.
        import pandas as pd

        ctx1._df_cache["call_ghost"] = pd.DataFrame({"a": [1]})

        list(run_agent_turn("q1", ctx1))
        list(run_agent_turn("q2", ctx2))

        # 두 context는 동일 객체가 아니어야 한다 (factory_factory가 새 dict 생성).
        self.assertIsNot(ctx1._df_cache, ctx2._df_cache)
        # ctx2는 call_ghost를 본 적이 없어야 한다 (AGENT-07 stateless per turn).
        self.assertNotIn("call_ghost", ctx2._df_cache)


class DynamicPromptAndToolSpecTest(unittest.TestCase):
    """Configured allowed_tables must flow into the system prompt and the
    OpenAI tool specs (run_sql, pivot_to_wide) at turn time.

    Regression guard for making the table name user-configurable: the LLM
    must see the real configured table list, not a hardcoded literal.
    """

    def test_system_prompt_includes_configured_tables(self) -> None:
        prompt = _build_system_prompt(["benchmarks_2025", "archive"])
        self.assertIn("benchmarks_2025", prompt)
        self.assertIn("archive", prompt)
        self.assertNotIn("ufs_data", prompt)

    def test_system_prompt_empty_list_uses_placeholder(self) -> None:
        prompt = _build_system_prompt([])
        # Placeholder should not leak a concrete table name.
        self.assertNotIn("ufs_data", prompt)
        self.assertIn("configured", prompt.lower())

    def test_tool_specs_inject_configured_tables(self) -> None:
        specs = _build_openai_tools(["benchmarks_2025", "archive"])
        by_name = {s["function"]["name"]: s for s in specs}
        self.assertIn("run_sql", by_name)
        self.assertIn("pivot_to_wide", by_name)

        run_sql_spec = by_name["run_sql"]
        self.assertIn("benchmarks_2025", run_sql_spec["function"]["description"])
        sql_field = run_sql_spec["function"]["parameters"]["properties"]["sql"]
        self.assertIn("benchmarks_2025", sql_field["description"])
        self.assertNotIn("ufs_data", run_sql_spec["function"]["description"])

        pivot_spec = by_name["pivot_to_wide"]
        # pivot_to_wide uses the primary (first) table name.
        self.assertIn("benchmarks_2025", pivot_spec["function"]["description"])
        cat_field = pivot_spec["function"]["parameters"]["properties"]["category"]
        self.assertIn("benchmarks_2025", cat_field["description"])


if __name__ == "__main__":
    unittest.main()
