"""Tool 프로토콜 및 ToolResult 모델.

모든 Phase 2 도구는 Tool 프로토콜을 구조적으로 만족해야 한다(상속 불필요).
ToolResult는 BaseModel이므로 model_json_schema()를 통해 TOOL-07 스키마 생성에 재사용된다.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from app.core.agent.context import AgentContext


class ToolResult(BaseModel):
    """도구 실행 결과. 모델에 전달되는 문자열 + 선택적 구조화 페이로드."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    content: str = Field(
        description="Text returned to the model as the tool response.",
    )
    df_ref: str | None = Field(
        default=None,
        description="AgentContext._df_cache key when a DataFrame was stored.",
    )
    chart: Any | None = Field(
        default=None,
        description=(
            "plotly.graph_objects.Figure when the tool produced a chart "
            "(make_chart only)."
        ),
    )


@runtime_checkable
class Tool(Protocol):
    """도구는 name, args_model, __call__ 세 속성을 갖는 구조적 타입.

    args_model은 Pydantic BaseModel의 서브클래스이며 OpenAI 도구 스키마
    생성(TOOL-07)의 단일 진실 소스가 된다.
    """

    name: str

    @property
    def args_model(self) -> type[BaseModel]: ...

    def __call__(self, ctx: AgentContext, args: BaseModel) -> ToolResult: ...
