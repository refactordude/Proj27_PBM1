"""F5: Grafana 통합."""
from __future__ import annotations

import streamlit as st

from app.core.runtime import settings

s = settings()
st.title("📊 Grafana")

if not s.grafana.dashboards:
    st.info("등록된 대시보드가 없습니다. Settings에서 추가하세요.")
    st.stop()

names = [d.name for d in s.grafana.dashboards]
choice = st.selectbox("대시보드", names)
dash = next(d for d in s.grafana.dashboards if d.name == choice)

url = dash.url
if dash.kiosk:
    sep = "&" if "?" in url else "?"
    if "kiosk" not in url:
        url = f"{url}{sep}kiosk"

height = st.slider("높이 (px)", min_value=400, max_value=1400, value=800, step=50)
st.components.v1.iframe(url, height=height, scrolling=True)
st.caption(f"원본 URL: {dash.url}")
