"""Agent package — run_agent_turn과 AgentStep 공개 엔트리포인트.

loop 모듈 임포트는 지연(lazy)시킨다. app.core.config → app.core.agent.config 경로로
패키지 초기화가 트리거될 때 openai_adapter와의 순환 임포트를 피하기 위함이다.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["AgentStep", "run_agent_turn"]

if TYPE_CHECKING:  # pragma: no cover - 타입 체커 전용
    from app.core.agent.loop import AgentStep, run_agent_turn


def __getattr__(name: str) -> Any:
    if name in __all__:
        from app.core.agent import loop as _loop

        return getattr(_loop, name)
    raise AttributeError(f"module 'app.core.agent' has no attribute {name!r}")
