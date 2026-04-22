"""F3: 데이터 비교 (좌우 분할)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.core.logger import log_query
from app.core.runtime import resolve_selected_db, settings
from app.core.session import record_recent_query
from app.core.sql_safety import validate_and_sanitize

s = settings()
st.title("↔️ 데이터 비교")
st.caption("두 개의 SELECT 쿼리 결과를 좌/우로 비교합니다. 공통 키로 조인 비교할 수도 있습니다.")

db_name, adapter, err = resolve_selected_db(s)
if err:
    st.error(err)
    st.stop()
if adapter is None:
    st.warning("먼저 Settings에서 DB를 등록하세요.")
    st.stop()

col_a, col_b = st.columns(2)
with col_a:
    st.markdown("#### 쿼리 A")
    sql_a = st.text_area("SQL A", key="sql_a", height=160, placeholder="SELECT ...")
with col_b:
    st.markdown("#### 쿼리 B")
    sql_b = st.text_area("SQL B", key="sql_b", height=160, placeholder="SELECT ...")

join_key = st.text_input(
    "공통 키 (옵션, 쉼표로 구분) — 입력 시 A·B를 외부 조인하여 컬럼 단위 차이를 하이라이트합니다",
    value="",
)

run = st.button("두 쿼리 실행", type="primary")

if run:
    results: dict[str, pd.DataFrame | None] = {"A": None, "B": None}
    for label, sql in (("A", sql_a), ("B", sql_b)):
        check = validate_and_sanitize(sql, default_limit=s.app.query_row_limit)
        if not check.ok:
            st.error(f"쿼리 {label} 차단: {check.reason}")
            continue
        try:
            df = adapter.run_query(check.sanitized_sql)
            results[label] = df
            record_recent_query(
                check.sanitized_sql, db_name or "", len(df),
                max_items=s.app.recent_query_history,
            )
            log_query(
                user=st.session_state.get("user", "unknown"),
                database=db_name or "",
                sql=check.sanitized_sql,
                rows=len(df),
            )
        except Exception as exc:
            log_query(
                user=st.session_state.get("user", "unknown"),
                database=db_name or "",
                sql=check.sanitized_sql,
                error=str(exc),
            )
            st.error(f"쿼리 {label} 실패: {exc}")

    st.session_state["cmp_a"] = results["A"]
    st.session_state["cmp_b"] = results["B"]

df_a: pd.DataFrame | None = st.session_state.get("cmp_a")
df_b: pd.DataFrame | None = st.session_state.get("cmp_b")

if df_a is not None or df_b is not None:
    left, right = st.columns(2)
    with left:
        st.markdown(f"**A · {len(df_a) if df_a is not None else 0} rows**")
        if df_a is not None:
            st.dataframe(df_a, use_container_width=True, height=350)
    with right:
        st.markdown(f"**B · {len(df_b) if df_b is not None else 0} rows**")
        if df_b is not None:
            st.dataframe(df_b, use_container_width=True, height=350)

    if join_key.strip() and df_a is not None and df_b is not None:
        keys = [k.strip() for k in join_key.split(",") if k.strip()]
        missing = [
            k for k in keys
            if k not in df_a.columns or k not in df_b.columns
        ]
        if missing:
            st.warning(f"키 컬럼이 양쪽 모두에 없습니다: {missing}")
        else:
            st.subheader("조인 비교")
            merged = df_a.merge(
                df_b, how="outer", on=keys, suffixes=("_A", "_B"), indicator=True
            )
            st.write(
                f"A만: {(merged['_merge'] == 'left_only').sum()} · "
                f"B만: {(merged['_merge'] == 'right_only').sum()} · "
                f"공통: {(merged['_merge'] == 'both').sum()}"
            )

            common_cols = [c for c in df_a.columns if c in df_b.columns and c not in keys]

            def _highlight(row: pd.Series) -> list[str]:
                styles = ["" for _ in row.index]
                for c in common_cols:
                    ca, cb = f"{c}_A", f"{c}_B"
                    if ca in row.index and cb in row.index and row[ca] != row[cb]:
                        styles[list(row.index).index(ca)] = "background-color: #fff3cd"
                        styles[list(row.index).index(cb)] = "background-color: #fff3cd"
                return styles

            try:
                styled = merged.style.apply(_highlight, axis=1)
                st.dataframe(styled, use_container_width=True, height=500)
            except Exception:
                st.dataframe(merged, use_container_width=True, height=500)
