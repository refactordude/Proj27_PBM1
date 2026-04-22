"""long→wide 피벗 도구 (TOOL-03, UFS 스펙 §3).

ufs_data에서 InfoCatergory/Item으로 좁힌 long-form 결과를 받아
df.pivot_table(index='parameter', columns='PLATFORM_ID', values='Result',
               aggfunc='first')로 wide-form으로 변환하고
ctx._df_cache에 저장한 뒤 df_ref를 돌려준다.
"""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.core.agent.context import AgentContext
from app.core.agent.tools._base import ToolResult


class PivotToWideArgs(BaseModel):
    category: str = Field(
        ...,
        description=(
            "Filter value for ufs_data.InfoCatergory (DB column name is "
            "misspelled 'Catergory' — use the typo when calling)."
        ),
    )
    item: str = Field(
        ...,
        description="Filter value for ufs_data.Item.",
    )


def _sql_escape(s: str) -> str:
    return s.replace("'", "''")


class PivotToWideTool:
    name: str = "pivot_to_wide"
    args_model: type[BaseModel] = PivotToWideArgs
    description: str = (
        "Reshape long-form (parameter, PLATFORM_ID, Result) rows from ufs_data "
        "into a wide DataFrame with PLATFORM_ID as columns. Duplicates collapse "
        "via aggfunc='first'. Result is cached; df_ref is returned for "
        "normalize_result / make_chart."
    )

    def __call__(self, ctx: AgentContext, args: BaseModel) -> ToolResult:
        assert isinstance(args, PivotToWideArgs)
        table = ctx.config.allowed_tables[0] if ctx.config.allowed_tables else "ufs_data"
        esc_cat = _sql_escape(args.category)
        esc_item = _sql_escape(args.item)
        sql = (
            f"SELECT parameter, PLATFORM_ID, Result FROM {table} "
            f"WHERE InfoCatergory = '{esc_cat}' AND Item = '{esc_item}' "
            f"LIMIT {ctx.config.row_cap}"
        )
        df = ctx.db_adapter.run_query(sql)
        if df.empty:
            return ToolResult(
                content=(
                    f"No rows matched InfoCatergory={args.category!r}, "
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
