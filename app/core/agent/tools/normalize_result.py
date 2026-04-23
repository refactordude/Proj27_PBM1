"""UFS 스펙 §5 clean_result 적용 도구 (TOOL-04).

데이터 정제: hex→int, 정수/소수 파싱, 'None'/'nan'/'-'/'n/a'→NA,
'local=1,peer=2' 형태의 compound 값은 행 분할(parameter 컬럼에 _local/_peer
접미 — RESEARCH.md Open Question #1 결정사항). 결과는 data_ref 파생 키
f'{data_ref}:normalized'로 캐시에 저장하고 df_ref를 돌려준다.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from app.core.agent.context import AgentContext
from app.core.agent.tools._base import ToolResult

_HEX_RE = re.compile(r"^0x[0-9a-fA-F]+$")
_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d+\.\d+$")
_NULL_LIKE = {"None", "none", "nan", "NaN", "NAN", "", "-", "n/a", "N/A"}


def _is_compound(s: str) -> bool:
    """Return True only for strict `name1=value1,name2=value2[,...]` strings.

    Every comma-separated segment must contain an `=`; otherwise the value is
    treated as an opaque scalar (e.g. a CSV value `"x=foo,bar,y=baz"` where
    `bar` is part of the first value — we must not split on that comma and
    replace `bar` with NA). Strictly requires 2+ segments so a single `k=v`
    keeps its literal form. (WR-02)
    """
    if "," not in s or "=" not in s:
        return False
    parts = s.split(",")
    if len(parts) < 2:
        return False
    return all("=" in part for part in parts)


def _clean_cell(v: Any) -> Any:
    if v is pd.NA or (v is None) or (isinstance(v, float) and pd.isna(v)):
        return pd.NA
    s = str(v).strip()
    if s in _NULL_LIKE:
        return pd.NA
    if _HEX_RE.match(s):
        return int(s, 16)
    if _INT_RE.match(s):
        return int(s)
    if _FLOAT_RE.match(s):
        return float(s)
    return s


def _split_compound_rows(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """UFS §5 compound split: 'local=1,peer=2' → two rows with parameter/Item suffix."""
    target_col = "parameter" if "parameter" in df.columns else (
        "Item" if "Item" in df.columns else None
    )
    out_rows: list[dict] = []
    for _, row in df.iterrows():
        v = row[col]
        if isinstance(v, str) and _is_compound(v):
            for pair in v.split(","):
                # _is_compound guarantees every pair contains '=', but guard
                # anyway in case of future loosening. Skip malformed pairs so
                # they don't overwrite the parameter suffix with an empty key. (WR-02)
                if "=" not in pair:
                    continue
                k, _, val = pair.partition("=")
                k = k.strip()
                if not k:
                    continue
                new_row = row.to_dict()
                if target_col is not None:
                    new_row[target_col] = f"{row[target_col]}_{k}"
                new_row[col] = _clean_cell(val.strip())
                out_rows.append(new_row)
        else:
            new_row = row.to_dict()
            new_row[col] = _clean_cell(v)
            out_rows.append(new_row)
    return pd.DataFrame(out_rows).reset_index(drop=True)


class NormalizeResultArgs(BaseModel):
    data_ref: str = Field(
        ...,
        description=(
            "Reference returned by a previous tool (e.g. pivot_to_wide). The "
            "cached DataFrame is cleaned in place of the named ref and the new "
            "result is cached under '<data_ref>:normalized'."
        ),
    )


class NormalizeResultTool:
    name: str = "normalize_result"
    args_model: type[BaseModel] = NormalizeResultArgs
    description: str = (
        "Apply UFS spec §5 cleaning to a cached DataFrame: hex→int, numeric "
        "parsing, null-likes→NA, and compound 'local=…,peer=…' values split "
        "into rows with parameter suffix. Returns a new df_ref."
    )

    def __call__(self, ctx: AgentContext, args: BaseModel) -> ToolResult:
        assert isinstance(args, NormalizeResultArgs)
        src = ctx.get_df(args.data_ref)
        if src is None:
            return ToolResult(
                content=f"No DataFrame cached at {args.data_ref!r}."
            )
        if "Result" in src.columns:
            normalized = _split_compound_rows(src, "Result")
        else:
            normalized = src.map(_clean_cell)
        new_ref = f"{args.data_ref}:normalized"
        ctx.store_df(new_ref, normalized)
        return ToolResult(
            content=(
                f"Normalized {len(src)} → {len(normalized)} rows. "
                f"Cached as {new_ref}."
            ),
            df_ref=new_ref,
        )


normalize_result_tool = NormalizeResultTool()
