"""에이전트 도구 플랫 레지스트리 — Phase 3 루프가 import하는 진입점."""
from __future__ import annotations

from app.core.agent.tools._base import Tool
from app.core.agent.tools.get_schema import get_schema_tool
from app.core.agent.tools.get_schema_docs import get_schema_docs_tool
from app.core.agent.tools.make_chart import make_chart_tool
from app.core.agent.tools.normalize_result import normalize_result_tool
from app.core.agent.tools.pivot_to_wide import pivot_to_wide_tool
from app.core.agent.tools.run_sql import run_sql_tool

TOOL_REGISTRY: dict[str, Tool] = {
    t.name: t
    for t in (
        run_sql_tool,
        get_schema_tool,
        pivot_to_wide_tool,
        normalize_result_tool,
        get_schema_docs_tool,
        make_chart_tool,
    )
}

__all__ = ["TOOL_REGISTRY"]
