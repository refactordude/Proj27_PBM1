"""F4: AI 질의 (자연어 → SQL → 실행)."""
from __future__ import annotations

import time

import streamlit as st

from app.core.logger import log_llm, log_query
from app.core.runtime import resolve_selected_db, resolve_selected_llm, settings
from app.core.session import append_chat, get_chat_history, record_recent_query, reset_chat
from app.core.sql_safety import validate_and_sanitize
from app.utils.schema import extract_sql_from_response, summarize
from app.utils.viz import auto_chart

s = settings()
st.title("🤖 AI 질의")
st.caption("자연어로 질문하면 LLM이 SQL을 생성합니다. **실행 전에 반드시 SQL을 확인하세요.**")

db_name, db_adapter, db_err = resolve_selected_db(s)
llm_name, llm_adapter, llm_err = resolve_selected_llm(s)

if db_err:
    st.error(db_err)
if llm_err:
    st.error(llm_err)
if db_adapter is None or llm_adapter is None:
    st.warning("Settings에서 DB와 LLM을 모두 등록해야 합니다.")
    st.stop()

if st.button("🧹 대화 초기화"):
    reset_chat()
    st.rerun()

for turn in get_chat_history():
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])
        sql = turn.get("sql")
        if sql:
            st.code(sql, language="sql")

question = st.chat_input("데이터에 대해 무엇이든 물어보세요…")

if question:
    append_chat("user", question)
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner(f"스키마 요약 및 {llm_name} 호출 중..."):
            try:
                schema = db_adapter.get_schema()
            except Exception as exc:
                schema = {}
                st.warning(f"스키마 로드 실패 ({exc}). 스키마 없이 진행합니다.")
            schema_text = summarize(schema)

            start = time.perf_counter()
            try:
                raw = llm_adapter.generate_sql(
                    question=question,
                    schema_summary=schema_text,
                    history=[h for h in get_chat_history() if h["role"] in {"user", "assistant"}],
                )
                duration = (time.perf_counter() - start) * 1000
                sql_only = extract_sql_from_response(raw)
                log_llm(
                    user=st.session_state.get("user", "unknown"),
                    model=llm_name or "",
                    question=question,
                    sql=sql_only,
                    duration_ms=duration,
                )
            except Exception as exc:
                log_llm(
                    user=st.session_state.get("user", "unknown"),
                    model=llm_name or "",
                    question=question,
                    error=str(exc),
                )
                st.error(f"LLM 호출 실패: {exc}")
                st.stop()

        st.markdown(raw)
        st.code(sql_only, language="sql")
        append_chat("assistant", raw, sql=sql_only)
        st.session_state["pending_sql"] = sql_only

pending_sql: str | None = st.session_state.get("pending_sql")
if pending_sql:
    st.divider()
    st.subheader("SQL 실행 확인")
    edited = st.text_area(
        "실행 전 SQL 편집 가능",
        value=pending_sql,
        key="pending_sql_edit",
        height=140,
    )
    col1, col2 = st.columns([1, 5])
    if col1.button("✅ 실행", type="primary"):
        check = validate_and_sanitize(edited, default_limit=s.app.query_row_limit)
        if not check.ok:
            st.error(f"SQL 차단됨: {check.reason}")
        else:
            start = time.perf_counter()
            try:
                df = db_adapter.run_query(check.sanitized_sql)
                duration = (time.perf_counter() - start) * 1000
                record_recent_query(
                    check.sanitized_sql, db_name or "", len(df),
                    max_items=s.app.recent_query_history,
                )
                log_query(
                    user=st.session_state.get("user", "unknown"),
                    database=db_name or "",
                    sql=check.sanitized_sql,
                    rows=len(df),
                    duration_ms=duration,
                )
                st.success(f"{len(df):,} rows · {duration:.0f} ms")
                st.dataframe(df, use_container_width=True, height=400)
                chart = auto_chart(df)
                if chart is not None:
                    st.plotly_chart(chart, use_container_width=True)
                st.session_state["pending_sql"] = None
            except Exception as exc:
                log_query(
                    user=st.session_state.get("user", "unknown"),
                    database=db_name or "",
                    sql=check.sanitized_sql,
                    error=str(exc),
                )
                st.error(f"실행 실패: {exc}")
    if col2.button("🗑️ 버리기"):
        st.session_state["pending_sql"] = None
        st.rerun()
