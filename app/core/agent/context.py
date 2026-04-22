"""에이전트 턴 단위 실행 컨텍스트 (DI 컨테이너).

home.py가 매 턴마다 새로 구성하고 run_agent_turn()에 주입한다.
_df_cache는 인스턴스 속성이므로 턴 간 공유되지 않는다(AGENT-07 stateless-per-turn).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.adapters.db.base import DBAdapter
from app.adapters.llm.base import LLMAdapter
from app.core.agent.config import AgentConfig


@dataclass
class AgentContext:
    db_adapter: DBAdapter
    llm_adapter: LLMAdapter
    db_name: str
    user: str
    config: AgentConfig
    _df_cache: dict[str, pd.DataFrame] = field(default_factory=dict)

    def store_df(self, tool_call_id: str, df: pd.DataFrame) -> None:
        """Tool-call_id로 DataFrame을 턴-로컬 캐시에 저장."""
        self._df_cache[tool_call_id] = df

    def get_df(self, tool_call_id: str) -> pd.DataFrame | None:
        """저장된 DataFrame을 반환하거나, 없으면 None."""
        return self._df_cache.get(tool_call_id)
