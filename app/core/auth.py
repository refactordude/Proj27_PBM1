"""streamlit-authenticator 래퍼.

auth.yaml에서 사용자 정보를 읽어 로그인 UI를 표시하고, 인증 결과를
session_state에 "user"로 보관한다.
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
import streamlit_authenticator as stauth
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _auth_path() -> Path:
    override = os.environ.get("AUTH_PATH")
    return Path(override) if override else _REPO_ROOT / "config" / "auth.yaml"


@st.cache_resource(show_spinner=False)
def _authenticator() -> stauth.Authenticate:
    with _auth_path().open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return stauth.Authenticate(
        credentials=cfg["credentials"],
        cookie_name=cfg["cookie"]["name"],
        cookie_key=cfg["cookie"]["key"],
        cookie_expiry_days=cfg["cookie"].get("expiry_days", 7),
    )


def require_login() -> str:
    """
    로그인 폼을 렌더한다. 성공 시 로그인한 username을 반환하고, 실패 시
    st.stop()으로 이후 페이지 렌더를 중단한다.
    """
    authenticator = _authenticator()
    try:
        authenticator.login(location="main")
    except TypeError:
        # 구버전 호환
        authenticator.login("Login", "main")

    status = st.session_state.get("authentication_status")
    if status is False:
        st.error("사용자명 또는 비밀번호가 올바르지 않습니다.")
        st.stop()
    if status is None:
        st.info("로그인이 필요합니다.")
        st.stop()

    username = st.session_state.get("username") or "unknown"
    st.session_state["user"] = username
    with st.sidebar:
        st.write(f"**사용자:** {st.session_state.get('name', username)}")
        try:
            authenticator.logout(location="sidebar")
        except TypeError:
            authenticator.logout("Logout", "sidebar")
    return username
