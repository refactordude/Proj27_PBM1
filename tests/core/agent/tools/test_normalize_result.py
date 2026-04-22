"""TOOL-04 normalize_result 단위 테스트: clean_cell / pydantic / compound row-split (TEST-01)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import pandas as pd
from pydantic import ValidationError

from app.core.agent.config import AgentConfig
from app.core.agent.context import AgentContext
from app.core.agent.tools._base import Tool
from app.core.agent.tools.normalize_result import (
    NormalizeResultArgs,
    _clean_cell,
    normalize_result_tool,
)


def _mk_ctx() -> AgentContext:
    return AgentContext(
        db_adapter=MagicMock(),
        llm_adapter=MagicMock(),
        db_name="unit_db",
        user="alice",
        config=AgentConfig(),
    )


class CleanCellTransformationsTest(unittest.TestCase):
    def test_hex(self) -> None:
        self.assertEqual(_clean_cell("0x10"), 16)
        self.assertEqual(_clean_cell("0x1D1C0000000"), 2000381018112)

    def test_int(self) -> None:
        self.assertEqual(_clean_cell("100"), 100)
        self.assertEqual(_clean_cell("-42"), -42)

    def test_float(self) -> None:
        self.assertEqual(_clean_cell("0.5"), 0.5)
        self.assertEqual(_clean_cell("-3.14"), -3.14)

    def test_null_like(self) -> None:
        for null_like in ["None", "none", "nan", "NaN", "", "-", "n/a", "N/A"]:
            self.assertTrue(pd.isna(_clean_cell(null_like)), null_like)

    def test_pass_through(self) -> None:
        self.assertEqual(_clean_cell("abc"), "abc")
        self.assertEqual(_clean_cell("1.2.3"), "1.2.3")  # not a valid float

    def test_pandas_na(self) -> None:
        self.assertTrue(pd.isna(_clean_cell(pd.NA)))
        self.assertTrue(pd.isna(_clean_cell(None)))


class NormalizePydanticTest(unittest.TestCase):
    def test_missing_data_ref(self) -> None:
        with self.assertRaises(ValidationError):
            NormalizeResultArgs()  # type: ignore[call-arg]


class CompoundSplitDomainEdgeTest(unittest.TestCase):
    def test_local_peer_row_split(self) -> None:
        src = pd.DataFrame(
            {
                "parameter": ["wb_enable"],
                "PLATFORM_ID": ["A"],
                "Result": ["local=1,peer=2"],
            }
        )
        ctx = _mk_ctx()
        ctx.store_df("call_src", src)
        result = normalize_result_tool(ctx, NormalizeResultArgs(data_ref="call_src"))
        self.assertEqual(result.df_ref, "call_src:normalized")
        norm = ctx.get_df("call_src:normalized")
        self.assertEqual(len(norm), 2)
        params = sorted(norm["parameter"].tolist())
        self.assertEqual(params, ["wb_enable_local", "wb_enable_peer"])
        results = sorted(norm["Result"].tolist())
        self.assertEqual(results, [1, 2])

    def test_non_compound_value_with_embedded_comma_preserved(self) -> None:
        """WR-02 regression: a Result string whose value contains a comma but
        is not uniformly `k=v,k=v,...` must NOT be split. The previous regex
        matched `x=foo,bar,y=baz` and silently turned the middle `bar` into a
        parameter-suffix row with NA Result — destroying real data.
        """
        src = pd.DataFrame(
            {
                "parameter": ["opaque"],
                "PLATFORM_ID": ["A"],
                "Result": ["x=foo,bar,y=baz"],
            }
        )
        ctx = _mk_ctx()
        ctx.store_df("call_opaque", src)
        normalize_result_tool(
            ctx, NormalizeResultArgs(data_ref="call_opaque")
        )
        norm = ctx.get_df("call_opaque:normalized")
        # One row in, one row out — no split. Original value preserved verbatim.
        self.assertEqual(len(norm), 1)
        self.assertEqual(norm.iloc[0]["parameter"], "opaque")
        self.assertEqual(norm.iloc[0]["Result"], "x=foo,bar,y=baz")


class LongFormHexTest(unittest.TestCase):
    def test_hex_result_parsed(self) -> None:
        src = pd.DataFrame(
            {
                "parameter": ["capacity"],
                "PLATFORM_ID": ["A"],
                "Result": ["0x1D1C0000000"],
            }
        )
        ctx = _mk_ctx()
        ctx.store_df("call_hex", src)
        normalize_result_tool(ctx, NormalizeResultArgs(data_ref="call_hex"))
        norm = ctx.get_df("call_hex:normalized")
        self.assertEqual(norm.iloc[0]["Result"], 2000381018112)


class WideFormElementwiseTest(unittest.TestCase):
    def test_wide_form_mapped(self) -> None:
        src = pd.DataFrame(
            {"A": ["0x10", "abc"], "B": ["100", "None"]},
            index=["p1", "p2"],
        )
        src.index.name = "parameter_wide"  # neither 'parameter' nor 'Item' column
        ctx = _mk_ctx()
        ctx.store_df("call_wide", src)
        result = normalize_result_tool(ctx, NormalizeResultArgs(data_ref="call_wide"))
        norm = ctx.get_df("call_wide:normalized")
        self.assertEqual(norm.loc["p1", "A"], 16)
        self.assertEqual(norm.loc["p2", "A"], "abc")
        self.assertEqual(norm.loc["p1", "B"], 100)
        self.assertTrue(pd.isna(norm.loc["p2", "B"]))
        self.assertEqual(result.df_ref, "call_wide:normalized")


class MissingRefTest(unittest.TestCase):
    def test_no_crash_when_ref_missing(self) -> None:
        ctx = _mk_ctx()
        result = normalize_result_tool(
            ctx, NormalizeResultArgs(data_ref="never_cached")
        )
        self.assertTrue(result.content.startswith("No DataFrame cached"))
        self.assertIsNone(result.df_ref)


class DerivedRefFormatTest(unittest.TestCase):
    def test_format(self) -> None:
        src = pd.DataFrame({"x": [1]})
        ctx = _mk_ctx()
        ctx.store_df("call_src", src)
        result = normalize_result_tool(ctx, NormalizeResultArgs(data_ref="call_src"))
        self.assertEqual(result.df_ref, "call_src:normalized")


class NormalizeProtocolTest(unittest.TestCase):
    def test_is_a_tool(self) -> None:
        self.assertIsInstance(normalize_result_tool, Tool)


if __name__ == "__main__":
    unittest.main()
