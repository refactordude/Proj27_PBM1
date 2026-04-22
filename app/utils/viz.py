"""결과 DataFrame에 대한 기본 시각화 제안."""
from __future__ import annotations

import pandas as pd
import plotly.express as px


def auto_chart(df: pd.DataFrame):
    """
    간단한 휴리스틱으로 차트 유형을 추천한다.
    - 2 컬럼 (문자+숫자): bar
    - 날짜 + 숫자: line
    - 숫자 2개: scatter
    - 그 외: None (차트 생략)
    """
    if df is None or df.empty or len(df.columns) < 2:
        return None

    cols = df.columns.tolist()
    first, second = df[cols[0]], df[cols[1]]

    if pd.api.types.is_datetime64_any_dtype(first) and pd.api.types.is_numeric_dtype(second):
        return px.line(df, x=cols[0], y=cols[1], title="자동 추천: 라인 차트")

    if pd.api.types.is_numeric_dtype(first) and pd.api.types.is_numeric_dtype(second):
        return px.scatter(df, x=cols[0], y=cols[1], title="자동 추천: 스캐터 차트")

    if (
        not pd.api.types.is_numeric_dtype(first)
        and pd.api.types.is_numeric_dtype(second)
        and len(df) <= 100
    ):
        return px.bar(df, x=cols[0], y=cols[1], title="자동 추천: 막대 차트")

    return None
