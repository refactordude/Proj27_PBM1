"""F6: 설정 (DB/LLM CRUD + 연결 테스트)."""
from __future__ import annotations

import streamlit as st

from app.adapters.db.registry import build_adapter as build_db, supported_types as db_types
from app.adapters.llm.registry import build_adapter as build_llm, supported_types as llm_types
from app.core.config import (
    DatabaseConfig,
    LLMConfig,
    save_settings,
)
from app.core.runtime import invalidate_settings, settings

s = settings()
st.title("⚙️ 설정")
st.caption("여기서 추가한 DB·LLM 정보는 `config/settings.yaml`에 저장됩니다.")

tab_db, tab_llm, tab_app = st.tabs(
    ["데이터베이스", "LLM 모델", "앱 기본값"]
)

# ----- Databases -----------------------------------------------------------
with tab_db:
    st.subheader("등록된 DB")
    for i, db in enumerate(list(s.databases)):
        with st.expander(f"{db.name} ({db.type} · {db.host}:{db.port}/{db.database})"):
            c1, c2, c3 = st.columns([1, 1, 4])
            if c1.button("연결 테스트", key=f"test_db_{i}"):
                try:
                    ok, msg = build_db(db).test_connection()
                    (st.success if ok else st.error)(msg)
                except Exception as exc:
                    st.error(str(exc))
            if c2.button("삭제", key=f"del_db_{i}"):
                s.databases.pop(i)
                save_settings(s)
                invalidate_settings()
                st.rerun()
            c3.caption(f"readonly={db.readonly}")

    st.divider()
    st.subheader("새 DB 추가")
    with st.form("new_db"):
        name = st.text_input("이름")
        col1, col2 = st.columns(2)
        dbtype = col1.selectbox("타입", db_types())
        host = col2.text_input("호스트", value="localhost")
        col3, col4 = st.columns(2)
        port = col3.number_input("포트", min_value=1, max_value=65535, value=3306)
        database = col4.text_input("DB 이름")
        col5, col6 = st.columns(2)
        user = col5.text_input("사용자")
        password = col6.text_input("비밀번호", type="password")
        readonly = st.checkbox("읽기전용 (READ ONLY transaction 강제)", value=True)
        if st.form_submit_button("추가"):
            if not name:
                st.error("이름은 필수입니다.")
            elif any(d.name == name for d in s.databases):
                st.error("같은 이름의 DB가 이미 있습니다.")
            else:
                s.databases.append(
                    DatabaseConfig(
                        name=name, type=dbtype, host=host, port=int(port),
                        database=database, user=user, password=password,
                        readonly=readonly,
                    )
                )
                save_settings(s)
                invalidate_settings()
                st.success("추가됨")
                st.rerun()

# ----- LLMs -----------------------------------------------------------------
with tab_llm:
    st.subheader("등록된 LLM")
    for i, m in enumerate(list(s.llms)):
        with st.expander(f"{m.name} ({m.type} · {m.model or '-'})"):
            c1, c2, c3 = st.columns([1, 1, 4])
            if c1.button("연결 테스트", key=f"test_llm_{i}"):
                try:
                    adapter = build_llm(m)
                    out = ""
                    for chunk in adapter.stream_text("ping"):
                        out += chunk
                        if len(out) > 5:
                            break
                    st.success(f"응답 수신: {out[:40]!r}")
                except Exception as exc:
                    st.error(str(exc))
            if c2.button("삭제", key=f"del_llm_{i}"):
                s.llms.pop(i)
                save_settings(s)
                invalidate_settings()
                st.rerun()
            c3.caption(f"endpoint={m.endpoint or '(기본)'}")

    st.divider()
    st.subheader("새 LLM 추가")
    with st.form("new_llm"):
        name = st.text_input("이름", key="llm_name")
        col1, col2 = st.columns(2)
        ltype = col1.selectbox("타입", llm_types(), key="llm_type")
        model = col2.text_input("모델명 (예: gpt-4o-mini, llama3.1:8b)")
        endpoint = st.text_input(
            "Endpoint (로컬 LLM 등에서 사용, 예: http://localhost:11434)", value=""
        )
        api_key = st.text_input("API Key (비우면 환경변수 사용)", type="password")
        col3, col4 = st.columns(2)
        temperature = col3.number_input("Temperature", 0.0, 2.0, 0.0, 0.1)
        max_tokens = col4.number_input("Max Tokens", 100, 32000, 2000, 100)
        if st.form_submit_button("추가"):
            if not name:
                st.error("이름은 필수입니다.")
            elif any(m.name == name for m in s.llms):
                st.error("같은 이름의 LLM이 이미 있습니다.")
            else:
                s.llms.append(
                    LLMConfig(
                        name=name, type=ltype, model=model, endpoint=endpoint,
                        api_key=api_key, temperature=float(temperature),
                        max_tokens=int(max_tokens),
                    )
                )
                save_settings(s)
                invalidate_settings()
                st.success("추가됨")
                st.rerun()

# ----- App defaults ---------------------------------------------------------
with tab_app:
    st.subheader("기본값 / 동작")
    db_names = ["(선택 없음)"] + [d.name for d in s.databases]
    llm_names = ["(선택 없음)"] + [m.name for m in s.llms]

    def _idx(lst, value):
        return lst.index(value) if value in lst else 0

    default_db = st.selectbox(
        "기본 DB", db_names, index=_idx(db_names, s.app.default_database or "(선택 없음)")
    )
    default_llm = st.selectbox(
        "기본 LLM", llm_names, index=_idx(llm_names, s.app.default_llm or "(선택 없음)")
    )
    row_limit = st.number_input(
        "기본 row limit", 10, 1_000_000, s.app.query_row_limit, 100
    )
    hist = st.number_input(
        "최근 질의 보관 개수", 1, 200, s.app.recent_query_history, 1
    )
    if st.button("저장", type="primary"):
        s.app.default_database = "" if default_db == "(선택 없음)" else default_db
        s.app.default_llm = "" if default_llm == "(선택 없음)" else default_llm
        s.app.query_row_limit = int(row_limit)
        s.app.recent_query_history = int(hist)
        save_settings(s)
        invalidate_settings()
        st.success("저장됨")
