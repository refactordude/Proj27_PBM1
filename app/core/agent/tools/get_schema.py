"""DB 스키마 + key 컬럼 distinct 값 조회 도구 (TOOL-02).

에이전트가 턴의 맨 앞에서 호출해 ufs_data의 컬럼 이름·타입과
PLATFORM_ID, InfoCatergory(컬럼명 오타는 DB 원본 보존 — SAFE-07)의
distinct 값을 한 번에 받아 필터 인자 환각을 줄인다.
"""
from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict

from app.core.agent.context import AgentContext
from app.core.agent.tools._base import ToolResult


class GetSchemaArgs(BaseModel):
    """No-arg tool. Pydantic emits {'type':'object'} which OpenAI accepts."""

    model_config = ConfigDict(extra="forbid")


class GetSchemaTool:
    name: str = "get_schema"
    args_model: type[BaseModel] = GetSchemaArgs
    description: str = (
        "Return tables in the allowlist with their columns and the distinct "
        "values of PLATFORM_ID and InfoCatergory. Call once per turn before "
        "selecting filter arguments for pivot_to_wide / run_sql."
    )

    def __call__(self, ctx: AgentContext, args: BaseModel) -> ToolResult:
        assert isinstance(args, GetSchemaArgs)
        tables = ctx.config.allowed_tables
        schema = ctx.db_adapter.get_schema(tables=tables)
        target = tables[0] if tables else "ufs_data"

        distinct_platform: list[str] = []
        distinct_category: list[str] = []
        try:
            df_p = ctx.db_adapter.run_query(
                f"SELECT DISTINCT PLATFORM_ID FROM {target} LIMIT 500"
            )
            if "PLATFORM_ID" in df_p.columns:
                distinct_platform = (
                    df_p["PLATFORM_ID"].dropna().astype(str).tolist()
                )
        except Exception as exc:  # noqa: BLE001 — surface as partial payload
            distinct_platform = [f"(query failed: {exc})"]

        try:
            df_c = ctx.db_adapter.run_query(
                f"SELECT DISTINCT InfoCatergory FROM {target} LIMIT 500"
            )
            if "InfoCatergory" in df_c.columns:
                distinct_category = (
                    df_c["InfoCatergory"].dropna().astype(str).tolist()
                )
        except Exception as exc:  # noqa: BLE001
            distinct_category = [f"(query failed: {exc})"]

        payload = {
            "tables": {
                t: [c["name"] for c in cols] for t, cols in schema.items()
            },
            "columns_detail": schema,
            "distinct_PLATFORM_ID": distinct_platform,
            "distinct_InfoCatergory": distinct_category,
        }
        return ToolResult(
            content=json.dumps(payload, ensure_ascii=False, indent=2)
        )


get_schema_tool = GetSchemaTool()
