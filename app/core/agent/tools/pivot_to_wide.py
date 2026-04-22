"""long→wide 피벗 도구 (TOOL-03, UFS 스펙 §3).

허용 테이블(allowed_tables[0])에서 InfoCategory /Item으로 좁힌 long-form
결과를 받아 df.pivot_table(index='parameter', columns='PLATFORM_ID',
values='Result', aggfunc='first')로 wide-form으로 변환하고 ctx._df_cache에
저장한 뒤 df_ref를 돌려준다.
"""
from __future__ import annotations

import time
import uuid

from pydantic import BaseModel, Field

from app.core.agent.context import AgentContext
from app.core.agent.tools._allowlist import AllowlistError, _check_table_allowlist
from app.core.agent.tools._base import ToolResult
from app.core.logger import log_query
from app.core.sql_safety import validate_and_sanitize


class PivotToWideArgs(BaseModel):
    category: str = Field(
        ...,
        description=(
            "Filter value for the allowlist table's InfoCategory  column "
            "(DB column name is misspelled 'Catergory' — use the typo "
            "when calling)."
        ),
    )
    item: str = Field(
        ...,
        description="Filter value for the allowlist table's Item column.",
    )


def _sql_escape(s: str) -> str:
    return s.replace("'", "''")


class PivotToWideTool:
    name: str = "pivot_to_wide"
    args_model: type[BaseModel] = PivotToWideArgs
    description: str = (
        "Reshape long-form (parameter, PLATFORM_ID, Result) rows from the "
        "configured allowlist table into a wide DataFrame with PLATFORM_ID "
        "as columns. Duplicates collapse via aggfunc='first'. Result is "
        "cached; df_ref is returned for normalize_result / make_chart."
    )

    def describe_for(self, allowed_tables: list[str]) -> dict:
        """Build an OpenAI tool spec with the primary table injected."""
        primary = allowed_tables[0] if allowed_tables else "the allowlist table"
        schema = self.args_model.model_json_schema()
        schema["properties"]["category"]["description"] = (
            f"Filter value for {primary}.InfoCategory  (DB column name is "
            "misspelled 'Catergory' — use the typo when calling)."
        )
        schema["properties"]["item"]["description"] = (
            f"Filter value for {primary}.Item."
        )
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": (
                    "Reshape long-form (parameter, PLATFORM_ID, Result) rows "
                    f"from {primary} into a wide DataFrame with PLATFORM_ID "
                    "as columns. Duplicates collapse via aggfunc='first'. "
                    "Result is cached; df_ref is returned for "
                    "normalize_result / make_chart."
                ),
                "parameters": schema,
            },
        }

    def __call__(self, ctx: AgentContext, args: BaseModel) -> ToolResult:
        assert isinstance(args, PivotToWideArgs)
        if not ctx.config.allowed_tables:
            # Fail-closed before building SQL. Preserve the OBS-01 audit
            # invariant (one log_query entry per invocation) so downstream
            # log analysis does not see a silent gap.
            reason = "no table configured in allowed_tables"
            log_query(
                user=f"{ctx.user} [via pivot_to_wide]",
                database=ctx.db_name,
                sql="",
                rows=None,
                duration_ms=0.0,
                error=reason,
            )
            return ToolResult(content=f"SQL rejected: {reason}.")
        table = ctx.config.allowed_tables[0]
        esc_cat = _sql_escape(args.category)
        esc_item = _sql_escape(args.item)
        sql = (
            f"SELECT parameter, PLATFORM_ID, Result FROM {table} "
            f"WHERE InfoCategory  = '{esc_cat}' AND Item = '{esc_item}' "
            f"LIMIT {ctx.config.row_cap}"
        )
        # WR-03: route the generated SQL through the same two safety gates as
        # run_sql. The SQL shape is static and `table` comes from allowlist
        # config, so the current exposure is limited — but running both gates
        # here keeps a single source of truth and guards against future
        # drift (e.g. user-controlled table argument, multi-table allowlists).
        safety = validate_and_sanitize(sql, default_limit=ctx.config.row_cap)
        if not safety.ok:
            # WR-04: log even the rejected path so OBS-01 covers pivot_to_wide.
            log_query(
                user=f"{ctx.user} [via pivot_to_wide]",
                database=ctx.db_name,
                sql=sql,
                rows=None,
                duration_ms=0.0,
                error=safety.reason,
            )
            return ToolResult(content=f"SQL rejected: {safety.reason}")
        sanitized = safety.sanitized_sql
        try:
            _check_table_allowlist(sanitized, ctx.config.allowed_tables)
        except AllowlistError as exc:
            log_query(
                user=f"{ctx.user} [via pivot_to_wide]",
                database=ctx.db_name,
                sql=sanitized,
                rows=None,
                duration_ms=0.0,
                error=str(exc),
            )
            return ToolResult(content=f"SQL rejected: {exc}")
        start = time.perf_counter()
        try:
            df = ctx.db_adapter.run_query(sanitized)
        except Exception as exc:  # noqa: BLE001 — mirror run_sql's surface
            duration_ms = (time.perf_counter() - start) * 1000
            log_query(
                user=f"{ctx.user} [via pivot_to_wide]",
                database=ctx.db_name,
                sql=sanitized,
                rows=None,
                duration_ms=duration_ms,
                error=str(exc),
            )
            return ToolResult(
                content="Query failed: database error. Refine your SQL."
            )
        duration_ms = (time.perf_counter() - start) * 1000
        # WR-04: single log entry per pivot_to_wide invocation (not per internal
        # DB call — there is only one DB call on the success path).
        log_query(
            user=f"{ctx.user} [via pivot_to_wide]",
            database=ctx.db_name,
            sql=sanitized,
            rows=len(df),
            duration_ms=duration_ms,
            error=None,
        )
        if df.empty:
            return ToolResult(
                content=(
                    f"No rows matched InfoCategory ={args.category!r}, "
                    f"Item={args.item!r}."
                )
            )
        wide = df.pivot_table(
            index="parameter",
            columns="PLATFORM_ID",
            values="Result",
            aggfunc="first",
        )
        key = ctx.current_tool_call_id or uuid.uuid4().hex
        ctx.store_df(key, wide)
        return ToolResult(
            content=f"Pivoted to wide form: shape={wide.shape}, cached as {key}.",
            df_ref=key,
        )


pivot_to_wide_tool = PivotToWideTool()
