"""페이지에서 공통으로 쓰이는 현재 선택된 DB/LLM 어댑터 해석 로직."""
from __future__ import annotations

import streamlit as st

from app.adapters.db.base import DBAdapter
from app.adapters.db.registry import build_adapter as build_db
from app.adapters.llm.base import LLMAdapter
from app.adapters.llm.registry import build_adapter as build_llm
from app.core.config import Settings, find_database, find_llm, load_settings
from app.core.session import (
    get_selected_db,
    get_selected_llm,
    set_selected_db,
    set_selected_llm,
)


def settings() -> Settings:
    # 캐시 무효화 트리거용 카운터가 바뀌면 새로 로드한다.
    version = st.session_state.get("_settings_version", 0)
    return _load_settings_cached(version)


@st.cache_data(show_spinner=False)
def _load_settings_cached(version: int) -> Settings:
    return load_settings()


def invalidate_settings() -> None:
    st.session_state["_settings_version"] = st.session_state.get("_settings_version", 0) + 1
    _load_settings_cached.clear()


def resolve_selected_db(s: Settings) -> tuple[str | None, DBAdapter | None, str | None]:
    """
    (이름, adapter, 에러메시지). 선택이 없으면 기본값을 사용.
    어댑터 생성 실패 시 에러 메시지 반환.
    """
    name = get_selected_db() or s.app.default_database
    if not name and s.databases:
        name = s.databases[0].name
        set_selected_db(name)
    if not name:
        return None, None, None
    cfg = find_database(s, name)
    if cfg is None:
        return name, None, f"설정에서 DB '{name}'을 찾을 수 없습니다."
    try:
        return name, build_db(cfg), None
    except Exception as exc:
        return name, None, f"DB 어댑터 생성 실패: {exc}"


def resolve_selected_llm(s: Settings) -> tuple[str | None, LLMAdapter | None, str | None]:
    name = get_selected_llm() or s.app.default_llm
    if not name and s.llms:
        name = s.llms[0].name
        set_selected_llm(name)
    if not name:
        return None, None, None
    cfg = find_llm(s, name)
    if cfg is None:
        return name, None, f"설정에서 LLM '{name}'을 찾을 수 없습니다."
    try:
        return name, build_llm(cfg), None
    except Exception as exc:
        return name, None, f"LLM 어댑터 생성 실패: {exc}"


def sidebar_selectors(s: Settings, *, show_llm: bool = True) -> None:
    """사이드바에 DB/LLM 선택 박스를 렌더한다."""
    if s.databases:
        db_names = [d.name for d in s.databases]
        current = get_selected_db() or (s.app.default_database or db_names[0])
        if current not in db_names:
            current = db_names[0]
        chosen = st.sidebar.selectbox("데이터베이스", db_names, index=db_names.index(current))
        set_selected_db(chosen)
    else:
        st.sidebar.info("등록된 DB가 없습니다. Settings에서 추가하세요.")

    if show_llm:
        if s.llms:
            llm_names = [m.name for m in s.llms]
            current = get_selected_llm() or (s.app.default_llm or llm_names[0])
            if current not in llm_names:
                current = llm_names[0]
            chosen = st.sidebar.selectbox("LLM 모델", llm_names, index=llm_names.index(current))
            set_selected_llm(chosen)
        else:
            st.sidebar.info("등록된 LLM이 없습니다. Settings에서 추가하세요.")
