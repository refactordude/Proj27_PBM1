"""F2: 데이터 탐색 (Explorer)."""
from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from app.core.logger import log_query
from app.core.runtime import resolve_selected_db, settings
from app.core.session import record_recent_query
from app.core.sql_safety import validate_and_sanitize
from app.utils.export import to_csv_bytes, to_excel_bytes

s = settings()
st.title("🔍 데이터 탐색")

db_name, adapter, err = resolve_selected_db(s)
if err:
    st.error(err)
    st.stop()
if adapter is None:
    st.warning("먼저 Settings에서 DB를 등록하세요.")
    st.stop()

with st.spinner("테이블 목록을 가져오는 중..."):
    try:
        tables = adapter.list_tables()
    except Exception as exc:
        st.error(f"테이블 목록 조회 실패: {exc}")
        st.stop()

if not tables:
    st.info("테이블이 없습니다.")
    st.stop()

col_l, col_r = st.columns([1, 3])
with col_l:
    table = st.selectbox("테이블", tables)
    limit = st.number_input(
        "최대 행 수", min_value=10, max_value=100_000, value=s.app.query_row_limit, step=100
    )
with col_r:
    search = st.text_input("검색 (현재 페이지 결과 내 필터)", placeholder="키워드…")

with st.spinner("스키마 로드 중..."):
    try:
        schema = adapter.get_schema([table])
    except Exception as exc:
        st.error(f"스키마 조회 실패: {exc}")
        st.stop()

columns = [c["name"] for c in schema.get(table, [])]
selected_cols = st.multiselect("컬럼 선택 (비우면 전체)", columns)

where_clause = st.text_input(
    "WHERE 절 (선택, 예: `created_at >= '2026-01-01' AND region = 'KR'`)",
    value="",
)
order_by = st.text_input("ORDER BY 절 (선택, 예: `created_at DESC`)", value="")

col_list = ", ".join(f"`{c}`" for c in selected_cols) if selected_cols else "*"
sql = f"SELECT {col_list} FROM `{table}`"
if where_clause.strip():
    sql += f" WHERE {where_clause.strip()}"
if order_by.strip():
    sql += f" ORDER BY {order_by.strip()}"
sql += f" LIMIT {int(limit)}"

st.code(sql, language="sql")

if "explorer_df" not in st.session_state:
    st.session_state.explorer_df = None

if st.button("실행", type="primary"):
    result = validate_and_sanitize(sql, default_limit=int(limit))
    if not result.ok:
        st.error(f"SQL 차단됨: {result.reason}")
    else:
        start = time.perf_counter()
        try:
            df = adapter.run_query(result.sanitized_sql)
            duration = (time.perf_counter() - start) * 1000
            st.session_state.explorer_df = df
            record_recent_query(
                result.sanitized_sql, db_name or "", len(df),
                max_items=s.app.recent_query_history,
            )
            log_query(
                user=st.session_state.get("user", "unknown"),
                database=db_name or "",
                sql=result.sanitized_sql,
                rows=len(df),
                duration_ms=duration,
            )
            st.success(f"{len(df):,} rows · {duration:.0f} ms")
        except Exception as exc:
            log_query(
                user=st.session_state.get("user", "unknown"),
                database=db_name or "",
                sql=result.sanitized_sql,
                error=str(exc),
            )
            st.error(f"쿼리 실패: {exc}")

df: pd.DataFrame | None = st.session_state.explorer_df
if df is not None:
    view = df
    if search:
        mask = view.astype(str).apply(lambda c: c.str.contains(search, case=False, na=False))
        view = view[mask.any(axis=1)]
    st.dataframe(view, use_container_width=True, height=500)

    c1, c2 = st.columns(2)
    c1.download_button(
        "CSV 다운로드",
        data=to_csv_bytes(view),
        file_name=f"{table}.csv",
        mime="text/csv",
    )
    c2.download_button(
        "Excel 다운로드",
        data=to_excel_bytes(view),
        file_name=f"{table}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
