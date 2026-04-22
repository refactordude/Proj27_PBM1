"""Streamlit session_state 헬퍼."""
from __future__ import annotations

from collections import deque
from typing import Any

import streamlit as st

_CHAT_HISTORY_KEY = "chat_history"
_RECENT_QUERIES_KEY = "recent_queries"
_SELECTED_DB_KEY = "selected_db"
_SELECTED_LLM_KEY = "selected_llm"


def get_chat_history() -> list[dict[str, Any]]:
    return st.session_state.setdefault(_CHAT_HISTORY_KEY, [])


def append_chat(role: str, content: str, **extra: Any) -> None:
    history = get_chat_history()
    history.append({"role": role, "content": content, **extra})


def reset_chat() -> None:
    st.session_state[_CHAT_HISTORY_KEY] = []


def record_recent_query(sql: str, database: str, rows: int | None, *, max_items: int = 20) -> None:
    bucket: deque = st.session_state.setdefault(_RECENT_QUERIES_KEY, deque(maxlen=max_items))
    if bucket.maxlen != max_items:
        new_bucket: deque = deque(bucket, maxlen=max_items)
        st.session_state[_RECENT_QUERIES_KEY] = new_bucket
        bucket = new_bucket
    bucket.appendleft({"sql": sql, "database": database, "rows": rows})


def recent_queries() -> list[dict[str, Any]]:
    bucket = st.session_state.get(_RECENT_QUERIES_KEY)
    return list(bucket) if bucket else []


def get_selected_db(default: str | None = None) -> str | None:
    return st.session_state.get(_SELECTED_DB_KEY, default)


def set_selected_db(name: str | None) -> None:
    st.session_state[_SELECTED_DB_KEY] = name


def get_selected_llm(default: str | None = None) -> str | None:
    return st.session_state.get(_SELECTED_LLM_KEY, default)


def set_selected_llm(name: str | None) -> None:
    st.session_state[_SELECTED_LLM_KEY] = name
