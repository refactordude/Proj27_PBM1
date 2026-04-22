"""F1: 홈 / AI Q&A (Agentic).

st.chat_input → run_agent_turn(user_message, ctx) 루프 직접 구동.
AgentStep 이벤트를 st.status 컨테이너에 라이브 렌더, 최종 답변은
st.write_stream으로 흘려보낸 뒤 트레이스를 st.expander로 접는다.
"""
from __future__ import annotations

import time
from typing import Iterator

import streamlit as st

from app.core.agent import AgentStep, run_agent_turn
from app.core.agent.context import AgentContext
from app.core.runtime import resolve_selected_db, resolve_selected_llm, settings
from app.core.session import (
    append_agent_trace,
    append_chat,
    get_agent_trace,
    get_chat_history,
    recent_queries,
    reset_chat,
)


# ---------------------------------------------------------------------------
# 헬퍼 — Streamlit은 top-to-bottom 실행이므로 호출부보다 먼저 정의해야 한다.
# ---------------------------------------------------------------------------


def _render_step_live(step: AgentStep, status) -> None:
    """라이브 트레이스(st.status) 안에서 AgentStep 하나를 렌더.

    tool_call → 도구 이름과 SQL(run_sql일 때)을 노출.
    tool_result → 결과 첫 줄 또는 오류 메시지(UX-07: 트레이스백 금지).
    final_answer 텍스트 자체는 status 밖에서 write_stream으로 처리한다.
    """
    if step.step_type == "tool_call":
        status.write(f"🛠 **{step.tool_name}**(...)")
        if step.tool_name == "run_sql" and step.sql:
            status.code(step.sql, language="sql")
        label = {
            "run_sql": "Running SQL...",
            "make_chart": "Building chart...",
            "pivot_to_wide": "Pivoting...",
            "normalize_result": "Normalizing...",
            "get_schema": "Inspecting schema...",
            "get_schema_docs": "Reading spec...",
        }.get(step.tool_name or "", "Thinking...")
        status.update(label=label)
    elif step.step_type == "tool_result":
        if step.error:
            # UX-07: 사람이 읽을 수 있는 에러 라인만 — st.exception/st.error 금지.
            status.write(f"⚠ {step.tool_name}: {step.error}")
        else:
            first_line = (step.content or "").splitlines()[0][:120] if step.content else ""
            status.write(f"✓ {first_line}")
        if step.chart is not None:
            status.plotly_chart(step.chart, use_container_width=True)
    elif step.step_type == "final_answer":
        if step.error:
            status.write(f"⚠ {step.error}")


def _render_steps_static(steps: list[AgentStep]) -> None:
    """접힌 expander 안에서 step 리스트를 정적으로 렌더.

    과거 턴을 rerun에서 다시 그릴 때도 사용 — 라이브 버전과 구조가 동일하지만
    status 컨테이너를 참조하지 않는다.
    """
    for step in steps:
        if step.step_type == "tool_call":
            st.markdown(f"🛠 **{step.tool_name}**(...)")
            if step.tool_name == "run_sql" and step.sql:
                st.code(step.sql, language="sql")
        elif step.step_type == "tool_result":
            if step.error:
                st.markdown(f"⚠ {step.tool_name}: {step.error}")
            else:
                first_line = (
                    (step.content or "").splitlines()[0][:120] if step.content else ""
                )
                st.markdown(f"✓ {first_line}")
            if step.chart is not None:
                st.plotly_chart(step.chart, use_container_width=True)
        # final_answer는 expander 외부에 이미 렌더되었으므로 생략.


def _stream_text(text: str) -> Iterator[str]:
    """st.write_stream용 단어 단위 제너레이터 — 자연스러운 progressive reveal (UX-04)."""
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.02)


def _last_chart_from_steps(steps: list[AgentStep]):
    """가장 최근에 emit된 차트(Plotly Figure)를 반환. 없으면 None."""
    for step in reversed(steps):
        if step.chart is not None:
            return step.chart
    return None


def _render_recent_queries() -> None:
    """HOME-03: Recent-queries 패널 — Explorer/Compare 등이 기록한 쿼리를 노출."""
    st.divider()
    st.subheader("최근 질의")
    rq = recent_queries()
    if not rq:
        st.info("아직 이번 세션에서 실행한 쿼리가 없습니다.")
        return
    for item in rq[:10]:
        with st.expander(
            f"[{item.get('database', '')}] · {item.get('rows', '?')} rows"
        ):
            st.code(item.get("sql", ""), language="sql")


# ---------------------------------------------------------------------------
# 페이지 본문 (Streamlit top-level 실행)
# ---------------------------------------------------------------------------

s = settings()
st.title("🏠 홈")
st.caption("사내 데이터 플랫폼에 오신 것을 환영합니다.")

cols = st.columns(3)
cols[0].metric("등록된 DB", len(s.databases))
cols[1].metric("등록된 LLM", len(s.llms))
db_name, db_adapter, db_err = resolve_selected_db(s)
cols[2].metric("현재 DB", db_name or "없음")

st.divider()

st.subheader("🤖 AI 질의")
st.caption("자연어로 질문하면 에이전트가 SQL을 실행하고 차트까지 만들어 답합니다.")

llm_name, llm_adapter, llm_err = resolve_selected_llm(s)
if db_err:
    st.error(db_err)
if llm_err:
    st.error(llm_err)

# Early-exit 가드: DB 또는 LLM이 없으면 Q&A를 노출하지 않는다.
if db_adapter is None or llm_adapter is None:
    st.warning("Settings에서 DB와 LLM을 모두 등록해야 AI 질의를 사용할 수 있습니다.")
    _render_recent_queries()
    st.stop()

# SAFE-06: OpenAI 전용 가드 — OpenAIAdapter가 아니면 chat_input을 잠근다.
is_openai = llm_adapter.__class__.__name__ == "OpenAIAdapter"
if not is_openai:
    st.info(
        "이 Q&A는 v1에서 OpenAI 전용입니다 — "
        "Settings에서 OpenAI 기반 LLM을 선택하세요."
    )

# HOME-03 preserved: chat-reset button (label literal required by grep contract).
if st.button("🧹 대화 초기화"):
    reset_chat()
    # HOME-04: 트레이스 슬롯도 함께 초기화 — chat_history와 보조를 맞춘다.
    if "agent_trace_v1" in st.session_state:
        del st.session_state["agent_trace_v1"]
    st.rerun()

# HOME-04: 과거 턴 렌더 + 어시스턴트 메시지에 트레이스 expander 부착.
history = get_chat_history()
for turn_index, turn in enumerate(history):
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])
        if turn["role"] == "assistant":
            past_steps = get_agent_trace(turn_index)
            if past_steps:
                # UX-05: rerun 이후에도 차트가 보이도록 expander 위에 인라인 렌더.
                past_chart = _last_chart_from_steps(past_steps)
                if past_chart is not None:
                    st.plotly_chart(past_chart, use_container_width=True)
                with st.expander("Show reasoning", expanded=False):
                    _render_steps_static(past_steps)

# HOME-01 + SAFE-06: 단일 chat_input, OpenAI가 아니면 disabled=True.
user_msg = st.chat_input(
    "질문을 입력하세요...",
    disabled=not is_openai,
)

if user_msg and is_openai:
    # user 메시지를 먼저 히스토리에 기록하고 화면에 노출.
    append_chat("user", user_msg)
    with st.chat_message("user"):
        st.markdown(user_msg)

    # AgentContext 구성 — 매 턴 새로 생성 (AGENT-07 stateless-per-turn).
    ctx = AgentContext(
        db_adapter=db_adapter,
        llm_adapter=llm_adapter,
        db_name=db_name or "",
        user=st.session_state.get("user", "anonymous"),
        config=s.app.agent,
    )

    collected_steps: list[AgentStep] = []
    final_step: AgentStep | None = None
    generator_failed = False

    with st.chat_message("assistant"):
        status = st.status("Thinking...", expanded=True)
        with status:
            # UX-07: run_agent_turn이 첫 yield 전에 raise할 수 있다 (예: OpenAI
            # 클라이언트 초기화 실패). 트레이스백 누출을 막기 위해 try/except로
            # 감싸고, 민감한 예외 메시지는 st.error로 절대 노출하지 않는다.
            try:
                for step in run_agent_turn(user_msg, ctx):
                    collected_steps.append(step)
                    _render_step_live(step, status)
                    if step.step_type == "final_answer":
                        final_step = step
                        break
            except Exception:  # noqa: BLE001
                generator_failed = True
                status.update(
                    label="Error",
                    state="error",
                    expanded=False,
                )
            else:
                status.update(
                    label="Done" if final_step and not final_step.error else "Stopped",
                    state="complete",
                    expanded=False,
                )

        if generator_failed:
            # UX-07: 사용자에게는 트레이스백 없이 일관된 문구만 노출.
            st.error("Agent encountered an unexpected error. Check logs.")

        # 최종 텍스트 스트리밍 (UX-04).
        if final_step is not None:
            final_text = final_step.content or ""
            if final_step.budget_exhausted and not final_step.error:
                # UX-06: 예산 소진 강제 종료 시 접두어 삽입.
                prefix = (
                    f"*Stopped after {s.app.agent.max_steps} steps; "
                    f"here's what I found.*\n\n"
                )
                final_text = prefix + final_text
            st.write_stream(_stream_text(final_text))

            # UX-05: 차트 인라인 렌더 — 가장 최근에 emit된 Figure 1개.
            last_chart = _last_chart_from_steps(collected_steps)
            if last_chart is not None:
                st.plotly_chart(last_chart, use_container_width=True)

            # UX-03: 전체 트레이스를 접힌 expander로 제공.
            with st.expander("Show reasoning", expanded=False):
                _render_steps_static(collected_steps)

            # HOME-04: 히스토리/트레이스 영속화.
            append_chat("assistant", final_text)
            # assistant 메시지의 history 인덱스를 트레이스 키로 사용.
            assistant_index = len(get_chat_history()) - 1
            append_agent_trace(assistant_index, collected_steps)

    st.rerun()

_render_recent_queries()
