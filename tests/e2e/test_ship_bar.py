"""Phase 5 ship-bar E2E: 3 SHIP 시나리오 + 로그 위생 + sibling page import 스모크.

본 모듈은 **mocked OpenAI 클라이언트 + mocked DB adapter** 위에서
`run_agent_turn`을 전체 dispatch chain 그대로 실행한다. TOOL_REGISTRY는 **실제**
도구들을 사용하므로 pivot_to_wide / normalize_result / make_chart 는 진짜 코드가
호출되어 Plotly Figure 까지 만들어낸다.

- SHIP-01: wb_enable 비교 (run_sql → pivot_to_wide → make_chart(bar))
- SHIP-02: total_raw_device_capacity 비교 (run_sql → normalize_result → make_chart(bar))
- SHIP-03: life_time_estimation_a Samsung vs OPPO (run_sql → normalize_result → make_chart(bar))
- LogSanityTest: logs/queries.log, logs/llm.log 의 JSONL 위생 점검
- SiblingPagesImportTest: explorer/compare/settings_page 가 AST-parse 되는지 확인 (HOME-05)

TEST-05 규율에 따라 LLM 이 뱉어낸 SQL 문자열 자체는 assert 하지 않는다 —
도구 디스패치 순서, 차트 타입, final_answer 존재 여부만 검증한다.
"""
from __future__ import annotations

import ast
import json
import pathlib
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import plotly.graph_objects as go

from app.core.agent.config import AgentConfig
from app.core.agent.context import AgentContext
from app.core.agent.loop import run_agent_turn
from tests.fixtures.ufs_seed import (
    capacity_rows,
    lifetime_samsung_oppo_rows,
    wb_enable_rows,
)


# ---------------------------------------------------------------------------
# Mock response builders (loop 테스트와 동일한 패턴)
# ---------------------------------------------------------------------------


def _make_tool_call_response(
    *,
    tool_name: str,
    arguments: str,
    call_id: str,
    prompt_tokens: int = 100,
    completion_tokens: int = 20,
) -> MagicMock:
    """tool_calls=[1개]을 가진 ChatCompletion 응답 모형."""
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
    """tool_calls=None 인 최종 답변 응답 모형."""
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
    db_return_df: pd.DataFrame,
    max_steps: int = 5,
) -> tuple[AgentContext, MagicMock]:
    """mocked llm_adapter._client() + mocked db_adapter.run_query 를 가진 ctx."""
    cfg = AgentConfig(max_steps=max_steps, timeout_s=30)
    fake_client = MagicMock()
    fake_llm_adapter = MagicMock()
    fake_llm_adapter._client.return_value = fake_client
    # _resolve_model falls back to the adapter's config.model when AgentConfig
    # has no override (the new default). Pin a concrete string so log_llm stays
    # JSON serializable and the fixture mirrors real resolution behavior.
    fake_llm_adapter.config.model = "test-model"
    fake_db_adapter = MagicMock()
    fake_db_adapter.run_query = MagicMock(return_value=db_return_df)

    ctx = AgentContext(
        db_adapter=fake_db_adapter,
        llm_adapter=fake_llm_adapter,
        db_name="test_db",
        user="e2e_user",
        config=cfg,
    )
    return ctx, fake_client


def _tool_name_sequence(steps: list) -> list[str]:
    """tool_call step 의 tool_name 만 뽑아 순서를 보존한 list 로 반환."""
    return [s.tool_name for s in steps if s.step_type == "tool_call"]


def _find_chart_step(steps: list):
    """step.chart 가 plotly Figure 인 첫 step 을 반환(없으면 None)."""
    for s in steps:
        if s.chart is not None and isinstance(s.chart, go.Figure):
            return s
    return None


def _find_final_answer(steps: list):
    """마지막 final_answer step 을 반환."""
    for s in reversed(steps):
        if s.step_type == "final_answer":
            return s
    return None


# ---------------------------------------------------------------------------
# SHIP-01: wb_enable 비교 (run_sql → pivot_to_wide → make_chart(bar))
# ---------------------------------------------------------------------------


class ShipBar01WbEnableTest(unittest.TestCase):
    """SHIP-01: Compare wb_enable across all devices.

    Tool chain: run_sql → pivot_to_wide → make_chart(bar) → final answer.
    pivot_to_wide 내부에서 ctx.db_adapter.run_query(sql)를 호출하므로 DB 모의는
    pivot 가능한 shape(parameter / PLATFORM_ID / Result) 의 DataFrame 을 돌려줘야
    한다. 이를 위해 fixture 의 Item 컬럼을 parameter 로 rename 한다.
    """

    def test_ship01_dispatch_chain_and_chart(self) -> None:
        # Pivot-friendly DF: Item -> parameter 로 바꿔 pivot_to_wide 가 받아들일
        # shape 으로 만든다 (pivot_to_wide 는 index='parameter' 를 사용).
        pivot_df = wb_enable_rows().rename(columns={"Item": "parameter"})
        ctx, fake_client = _make_ctx(db_return_df=pivot_df)

        # Tool-call side_effect 순서: run_sql → pivot_to_wide → make_chart → final.
        # pivot_to_wide 는 tool_call_id 를 cache key 로 사용하므로, make_chart 는
        # data_ref="call_pivot" 로 참조한다 (우리가 call_id 를 통제한다).
        tool_resps = [
            _make_tool_call_response(
                tool_name="run_sql",
                arguments=json.dumps(
                    {"sql": "SELECT PLATFORM_ID, Result FROM ufs_data "
                            "WHERE Item = 'wb_enable'"}
                ),
                call_id="call_sql",
            ),
            _make_tool_call_response(
                tool_name="pivot_to_wide",
                arguments=json.dumps(
                    {"category": "Feature", "item": "wb_enable"}
                ),
                call_id="call_pivot",
            ),
            _make_tool_call_response(
                tool_name="make_chart",
                arguments=json.dumps(
                    {
                        "chart_type": "bar",
                        "data_ref": "call_pivot",
                        "title": "wb_enable across devices",
                    }
                ),
                call_id="call_chart",
            ),
        ]
        final_resp = _make_final_answer_response(
            "wb_enable values: SM-S918=1, SM-G998=0, PIXEL-8=1, IQOO-12=1; "
            "OPPO-FIND-X6 is None."
        )
        fake_client.chat.completions.create.side_effect = tool_resps + [final_resp]

        steps = list(run_agent_turn("Compare wb_enable across devices", ctx))

        # 1) Tool dispatch 순서 검증.
        self.assertEqual(
            _tool_name_sequence(steps),
            ["run_sql", "pivot_to_wide", "make_chart"],
        )

        # 2) 최종 답변이 존재하고 비어있지 않아야 한다.
        final_step = _find_final_answer(steps)
        self.assertIsNotNone(final_step)
        assert final_step is not None
        self.assertEqual(final_step.step_type, "final_answer")
        self.assertGreater(len(final_step.content), 0)
        self.assertFalse(final_step.budget_exhausted)

        # 3) 적어도 하나의 step 은 plotly Figure 를 갖고 있어야 한다.
        chart_step = _find_chart_step(steps)
        self.assertIsNotNone(chart_step)
        assert chart_step is not None
        self.assertIsInstance(chart_step.chart, go.Figure)

        # 4) raw Python traceback 이 content 에 섞여 들어가면 안 된다.
        for s in steps:
            self.assertNotIn("Traceback", s.content)


# ---------------------------------------------------------------------------
# SHIP-02: total_raw_device_capacity 비교 (run_sql → normalize_result → make_chart(bar))
# ---------------------------------------------------------------------------


class ShipBar02CapacityTest(unittest.TestCase):
    """SHIP-02: Which devices have the largest total_raw_device_capacity?

    Tool chain: run_sql → normalize_result → make_chart(bar) → final answer.
    normalize_result 는 ctx._df_cache[data_ref] 에서 읽기 때문에, run_sql 이 스스로
    캐시에 저장하지 않는 점을 보완하려고 테스트가 ctx._df_cache['seed'] 로 fixture
    를 사전 주입한다. normalize_result 는 결과를 'seed:normalized' 키로 저장하고,
    make_chart 는 그 키를 참조한다.
    """

    def test_ship02_dispatch_chain_and_chart(self) -> None:
        df = capacity_rows()
        ctx, fake_client = _make_ctx(db_return_df=df)

        # normalize_result 가 읽을 수 있도록 cache 선주입.
        ctx._df_cache["seed"] = df

        tool_resps = [
            _make_tool_call_response(
                tool_name="run_sql",
                arguments=json.dumps(
                    {"sql": "SELECT PLATFORM_ID, Result FROM ufs_data "
                            "WHERE Item = 'total_raw_device_capacity'"}
                ),
                call_id="call_sql",
            ),
            _make_tool_call_response(
                tool_name="normalize_result",
                arguments=json.dumps({"data_ref": "seed"}),
                call_id="call_norm",
            ),
            _make_tool_call_response(
                tool_name="make_chart",
                arguments=json.dumps(
                    {
                        "chart_type": "bar",
                        "data_ref": "seed:normalized",
                        "x": "PLATFORM_ID",
                        "y": "Result",
                        "title": "total_raw_device_capacity (bytes)",
                    }
                ),
                call_id="call_chart",
            ),
        ]
        final_resp = _make_final_answer_response(
            "Largest capacity: SM-S918 (~2TB); OPPO-FIND-X6 ~128GB; "
            "SM-G998 and IQOO-12 ~4GB; PIXEL-8 is None."
        )
        fake_client.chat.completions.create.side_effect = tool_resps + [final_resp]

        steps = list(run_agent_turn("Largest total_raw_device_capacity?", ctx))

        self.assertEqual(
            _tool_name_sequence(steps),
            ["run_sql", "normalize_result", "make_chart"],
        )

        final_step = _find_final_answer(steps)
        self.assertIsNotNone(final_step)
        assert final_step is not None
        self.assertGreater(len(final_step.content), 0)

        chart_step = _find_chart_step(steps)
        self.assertIsNotNone(chart_step)
        assert chart_step is not None
        self.assertIsInstance(chart_step.chart, go.Figure)

        for s in steps:
            self.assertNotIn("Traceback", s.content)


# ---------------------------------------------------------------------------
# SHIP-03: life_time_estimation_a Samsung vs OPPO
# ---------------------------------------------------------------------------


class ShipBar03LifetimeBrandCompareTest(unittest.TestCase):
    """SHIP-03: Compare life_time_estimation_a for Samsung vs OPPO devices.

    Tool chain: run_sql → normalize_result → make_chart → final answer.
    compound ('local=1,peer=2') 값이 섞여있어 normalize_result 가 row 분할을
    수행한다 — 결과 DataFrame 의 행 수는 입력보다 커진다.
    """

    def test_ship03_dispatch_chain_and_chart(self) -> None:
        df = lifetime_samsung_oppo_rows()
        ctx, fake_client = _make_ctx(db_return_df=df)

        ctx._df_cache["seed"] = df

        tool_resps = [
            _make_tool_call_response(
                tool_name="run_sql",
                arguments=json.dumps(
                    {"sql": "SELECT PLATFORM_ID, Result FROM ufs_data "
                            "WHERE Item = 'life_time_estimation_a'"}
                ),
                call_id="call_sql",
            ),
            _make_tool_call_response(
                tool_name="normalize_result",
                arguments=json.dumps({"data_ref": "seed"}),
                call_id="call_norm",
            ),
            _make_tool_call_response(
                tool_name="make_chart",
                arguments=json.dumps(
                    {
                        "chart_type": "bar",
                        "data_ref": "seed:normalized",
                        "x": "PLATFORM_ID",
                        "y": "Result",
                        "title": "life_time_estimation_a: Samsung vs OPPO",
                    }
                ),
                call_id="call_chart",
            ),
        ]
        final_resp = _make_final_answer_response(
            "Samsung (SM-S918=1, SM-G998=2) vs OPPO (FIND-X6 split local=1/peer=2; "
            "RENO-11=3). OPPO shows higher lifetime counters on average."
        )
        fake_client.chat.completions.create.side_effect = tool_resps + [final_resp]

        steps = list(run_agent_turn("Samsung vs OPPO life_time_estimation_a?", ctx))

        self.assertEqual(
            _tool_name_sequence(steps),
            ["run_sql", "normalize_result", "make_chart"],
        )

        final_step = _find_final_answer(steps)
        self.assertIsNotNone(final_step)
        assert final_step is not None
        self.assertGreater(len(final_step.content), 0)

        chart_step = _find_chart_step(steps)
        self.assertIsNotNone(chart_step)
        assert chart_step is not None
        self.assertIsInstance(chart_step.chart, go.Figure)

        for s in steps:
            self.assertNotIn("Traceback", s.content)


# ---------------------------------------------------------------------------
# Log sanity (SC5)
# ---------------------------------------------------------------------------


def _assert_jsonl_clean(testcase: unittest.TestCase, path: pathlib.Path) -> None:
    """주어진 파일의 모든 라인이 순수 JSONL 인지 + Traceback 미포함 + <1MB 인지."""
    if not path.exists():
        testcase.skipTest(f"{path} does not exist yet")
        return
    size = path.stat().st_size
    testcase.assertLess(
        size, 1_000_000, f"{path} is {size} bytes (>=1MB); rotate or truncate."
    )
    with path.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.rstrip("\n")
            if not line.strip():
                # 허용: blank line.
                continue
            testcase.assertNotIn(
                "Traceback", line, f"{path}:{lineno} contains a traceback"
            )
            try:
                parsed: Any = json.loads(line)
            except json.JSONDecodeError as exc:
                testcase.fail(
                    f"{path}:{lineno} is not valid JSON: {exc}\nline={line!r}"
                )
            else:
                testcase.assertIsInstance(parsed, dict)


class LogSanityTest(unittest.TestCase):
    """logs/queries.log, logs/llm.log 의 위생 검사."""

    _REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

    def test_queries_log_jsonl_clean(self) -> None:
        _assert_jsonl_clean(self, self._REPO_ROOT / "logs" / "queries.log")

    def test_llm_log_jsonl_clean(self) -> None:
        _assert_jsonl_clean(self, self._REPO_ROOT / "logs" / "llm.log")


# ---------------------------------------------------------------------------
# HOME-05: sibling pages AST parse smoke
# ---------------------------------------------------------------------------


class SiblingPagesImportTest(unittest.TestCase):
    """HOME-05 code-level smoke: explorer/compare/settings_page 가 AST-parse 되는지.

    실제 Streamlit runtime 검증은 VERIFICATION.md 의 human_needed 체크로 연기된다.
    """

    _REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

    def _assert_parses(self, relpath: str) -> None:
        p = self._REPO_ROOT / relpath
        self.assertTrue(p.exists(), f"{relpath} not found at {p}")
        content = p.read_text(encoding="utf-8")
        try:
            ast.parse(content)
        except SyntaxError as exc:  # pragma: no cover - only triggers on regression
            self.fail(f"{relpath} failed to AST-parse: {exc}")

    def test_explorer_ast(self) -> None:
        self._assert_parses("app/pages/explorer.py")

    def test_compare_ast(self) -> None:
        self._assert_parses("app/pages/compare.py")

    def test_settings_page_ast(self) -> None:
        self._assert_parses("app/pages/settings_page.py")


if __name__ == "__main__":
    unittest.main()
