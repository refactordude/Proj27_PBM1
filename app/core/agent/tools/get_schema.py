"""DB 스키마 + key 컬럼 distinct 값 조회 도구 (TOOL-02).

에이전트가 턴의 맨 앞에서 호출해 허용 테이블의 컬럼 이름·타입과
PLATFORM_ID, InfoCategory의
distinct 값을 한 번에 받아 필터 인자 환각을 줄인다.
"""
from __future__ import annotations

import json
import time

from pydantic import BaseModel, ConfigDict

from app.core.agent.context import AgentContext
from app.core.agent.tools._base import ToolResult
from app.core.logger import log_query


class GetSchemaArgs(BaseModel):
    """No-arg tool. Pydantic emits {'type':'object'} which OpenAI accepts."""

    model_config = ConfigDict(extra="forbid")


class GetSchemaTool:
    name: str = "get_schema"
    args_model: type[BaseModel] = GetSchemaArgs
    description: str = (
        "Return tables in the allowlist with their columns and the distinct "
        "values of PLATFORM_ID and InfoCategory . Call once per turn before "
        "selecting filter arguments for pivot_to_wide / run_sql."
    )

    def __call__(self, ctx: AgentContext, args: BaseModel) -> ToolResult:
        assert isinstance(args, GetSchemaArgs)
        tables = ctx.config.allowed_tables
        if not tables:
            return ToolResult(
                content=(
                    "get_schema unavailable: no table configured in "
                    "allowed_tables. Update Settings → 앱 기본값 → "
                    "에이전트 허용 테이블."
                )
            )
        target = tables[0]

        # WR-04: emit exactly ONE log_query entry per invocation covering the
        # whole get_schema round-trip (schema lookup + both DISTINCT queries),
        # not one per internal DB call. OBS-01 audit trail now includes
        # get_schema alongside run_sql.
        start = time.perf_counter()
        any_error: str | None = None
        schema: dict = {}
        distinct_platform: list[str] = []
        distinct_category: list[str] = []
        try:
            schema = ctx.db_adapter.get_schema(tables=tables)
        except Exception as exc:  # noqa: BLE001 — surface in log, keep partial payload
            any_error = f"get_schema failed: {exc}"

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
            any_error = (
                f"{any_error}; platform distinct failed: {exc}"
                if any_error
                else f"platform distinct failed: {exc}"
            )

        try:
            df_c = ctx.db_adapter.run_query(
                f"SELECT DISTINCT InfoCategory  FROM {target} LIMIT 500"
            )
            if "InfoCategory" in df_c.columns:
                distinct_category = (
                    df_c["InfoCategory"].dropna().astype(str).tolist()
                )
        except Exception as exc:  # noqa: BLE001
            distinct_category = [f"(query failed: {exc})"]
            any_error = (
                f"{any_error}; category distinct failed: {exc}"
                if any_error
                else f"category distinct failed: {exc}"
            )

        duration_ms = (time.perf_counter() - start) * 1000
        # `sql` field records the tool's activity (no LLM-generated SQL to log);
        # `rows` is the combined count of distinct values surfaced to the agent.
        log_query(
            user=f"{ctx.user} [via get_schema]",
            database=ctx.db_name,
            sql=f"[get_schema target={target}]",
            rows=len(distinct_platform) + len(distinct_category),
            duration_ms=duration_ms,
            error=any_error,
        )

        payload = {
            "tables": {
                t: [c["name"] for c in cols] for t, cols in schema.items()
            },
            "columns_detail": schema,
            "distinct_PLATFORM_ID": distinct_platform,
            "distinct_InfoCategory": distinct_category,
        }
        return ToolResult(
            content=json.dumps(payload, ensure_ascii=False, indent=2)
        )


get_schema_tool = GetSchemaTool()
