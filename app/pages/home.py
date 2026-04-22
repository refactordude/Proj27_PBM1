"""F1: 홈 / 대시보드."""
from __future__ import annotations

import streamlit as st

from app.core.runtime import resolve_selected_db, settings
from app.core.session import recent_queries

s = settings()
st.title("🏠 홈")
st.caption("사내 데이터 플랫폼에 오신 것을 환영합니다.")

cols = st.columns(3)
cols[0].metric("등록된 DB", len(s.databases))
cols[1].metric("등록된 LLM", len(s.llms))
db_name, _, _ = resolve_selected_db(s)
cols[2].metric("현재 DB", db_name or "없음")

st.divider()

st.subheader("최근 질의")
rq = recent_queries()
if not rq:
    st.info("아직 이번 세션에서 실행한 쿼리가 없습니다.")
else:
    for item in rq[:10]:
        with st.expander(
            f"[{item.get('database', '')}] · {item.get('rows', '?')} rows"
        ):
            st.code(item.get("sql", ""), language="sql")
