"""차트 생성 도구 — Plotly Figure를 ToolResult.chart로 반환."""
from __future__ import annotations

from typing import Literal

import plotly.express as px
from pydantic import BaseModel, Field

from app.core.agent.context import AgentContext
from app.core.agent.tools._base import ToolResult


class MakeChartArgs(BaseModel):
    chart_type: Literal["bar", "line", "scatter", "heatmap"] = Field(
        ..., description="Chart type to render"
    )
    data_ref: str = Field(
        ..., description="AgentContext._df_cache key pointing to the DataFrame to plot"
    )
    x: str | None = Field(
        default=None, description="Column name for x-axis (ignored for heatmap)"
    )
    y: str | None = Field(
        default=None, description="Column name for y-axis (ignored for heatmap)"
    )
    color: str | None = Field(
        default=None,
        description="Optional column name for color encoding (bar/line/scatter only)",
    )
    title: str | None = Field(default=None, description="Optional chart title")


class MakeChartTool:
    name = "make_chart"
    args_model = MakeChartArgs

    def __call__(self, ctx: AgentContext, args: MakeChartArgs) -> ToolResult:
        df = ctx._df_cache.get(args.data_ref)
        if df is None:
            return ToolResult(
                content=f"make_chart error: data_ref '{args.data_ref}' not found in cache"
            )
        try:
            if args.chart_type == "bar":
                fig = px.bar(df, x=args.x, y=args.y, color=args.color, title=args.title)
            elif args.chart_type == "line":
                fig = px.line(df, x=args.x, y=args.y, color=args.color, title=args.title)
            elif args.chart_type == "scatter":
                fig = px.scatter(df, x=args.x, y=args.y, color=args.color, title=args.title)
            else:  # heatmap
                fig = px.imshow(df, title=args.title)
        except Exception as e:  # plotly argument errors
            return ToolResult(content=f"make_chart error: {e}")

        title_note = f" with title: {args.title}" if args.title else ""
        return ToolResult(
            content=f"Rendered {args.chart_type} chart from data_ref={args.data_ref}{title_note}",
            chart=fig,
        )


make_chart_tool = MakeChartTool()
