"""Streamlit 진입점.

인증 → 사이드바 공통 요소 → st.navigation으로 페이지 라우팅.

실행:
    streamlit run app/main.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

# app 패키지 import를 위한 path 보정 (streamlit은 app/main.py를 직접 실행)
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

load_dotenv(_REPO_ROOT / ".env", override=False)

import streamlit as st  # noqa: E402

from app.core.auth import require_login  # noqa: E402
from app.core.runtime import settings, sidebar_selectors  # noqa: E402


def _build_nav():
    pages_dir = _REPO_ROOT / "app" / "pages"
    return st.navigation(
        {
            "탐색": [
                st.Page(str(pages_dir / "home.py"), title="홈", icon="🏠", default=True),
                st.Page(str(pages_dir / "explorer.py"), title="데이터 탐색", icon="🔍"),
                st.Page(str(pages_dir / "compare.py"), title="데이터 비교", icon="↔️"),
            ],
            "관리": [
                st.Page(str(pages_dir / "settings_page.py"), title="설정", icon="⚙️"),
            ],
        }
    )


def main() -> None:
    st.set_page_config(
        page_title="사내 데이터 플랫폼",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    require_login()
    s = settings()
    with st.sidebar:
        st.markdown("### 세션 설정")
    sidebar_selectors(s)
    page = _build_nav()
    page.run()


if __name__ == "__main__":
    main()
