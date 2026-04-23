"""에이전트 실행 컨텍스트 및 예산 설정.

에이전트 루프의 예산(max_steps, timeout_s 등)과 사용 모델을 단일
Pydantic 모델로 노출한다. 값은 config/settings.yaml → app.agent.* 경로로
주입되며 v1에서는 Settings UI로 편집하지 않는다(OBS-03).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """에이전트 루프 예산 및 모델 설정.

    YAML 경로: settings.yaml → app.agent.*
    v1에서는 Settings UI에서 편집하지 않고 YAML 파일 직접 편집만 허용한다.
    """

    model: str = Field(
        default="",
        description=(
            "OpenAI tool-capable model override. Empty string (default) means "
            "fall back to the currently-selected LLM's model (see "
            "LLMConfig.model in settings.yaml). Set this only when you want "
            "the agentic loop to run a *different* model from the one used "
            "for non-agent calls (AGENT-09 accuracy-escalation path)."
        ),
    )
    max_steps: int = Field(default=5, ge=1, le=20)
    row_cap: int = Field(default=200, ge=1, le=10000)
    timeout_s: int = Field(default=30, ge=5, le=300)
    allowed_tables: list[str] = Field(
        default_factory=lambda: ["ufs_data"],
        description="Table names run_sql is permitted to query.",
    )
    max_context_tokens: int = Field(default=30_000, ge=1000, le=1_000_000)
