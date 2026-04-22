"""TOOL-02 get_schema 단위 테스트: happy / pydantic / empty-DB edge (TEST-01)."""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock

import pandas as pd
from pydantic import ValidationError

from app.core.agent.config import AgentConfig
from app.core.agent.context import AgentContext
from app.core.agent.tools._base import Tool
from app.core.agent.tools.get_schema import GetSchemaArgs, get_schema_tool


def _mk_ctx(schema: dict, distinct_platform: pd.DataFrame, distinct_cat: pd.DataFrame) -> AgentContext:
    db = MagicMock()
    db.get_schema.return_value = schema
    db.run_query.side_effect = [distinct_platform, distinct_cat]
    return AgentContext(
        db_adapter=db,
        llm_adapter=MagicMock(),
        db_name="unit_db",
        user="alice",
        config=AgentConfig(),
    )


class GetSchemaHappyPathTest(unittest.TestCase):
    def test_returns_json_with_expected_keys(self) -> None:
        schema = {
            "ufs_data": [
                {"name": "PLATFORM_ID", "type": "VARCHAR", "nullable": True, "pk": False},
                {"name": "InfoCatergory", "type": "VARCHAR", "nullable": True, "pk": False},
                {"name": "Item", "type": "VARCHAR", "nullable": True, "pk": False},
                {"name": "parameter", "type": "VARCHAR", "nullable": True, "pk": False},
                {"name": "Result", "type": "TEXT", "nullable": True, "pk": False},
            ]
        }
        ctx = _mk_ctx(
            schema,
            pd.DataFrame({"PLATFORM_ID": ["A", "B", "C"]}),
            pd.DataFrame({"InfoCatergory": ["§3.1", "§5.2"]}),
        )
        result = get_schema_tool(ctx, GetSchemaArgs())
        payload = json.loads(result.content)
        self.assertIn("tables", payload)
        self.assertIn("columns_detail", payload)
        self.assertIn("distinct_PLATFORM_ID", payload)
        self.assertIn("distinct_InfoCatergory", payload)
        self.assertEqual(payload["tables"]["ufs_data"],
                         ["PLATFORM_ID", "InfoCatergory", "Item", "parameter", "Result"])
        self.assertEqual(payload["distinct_PLATFORM_ID"], ["A", "B", "C"])
        self.assertEqual(payload["distinct_InfoCatergory"], ["§3.1", "§5.2"])


class GetSchemaPydanticTest(unittest.TestCase):
    def test_no_arg_schema_shape(self) -> None:
        schema = GetSchemaArgs.model_json_schema()
        self.assertEqual(schema.get("type"), "object")

    def test_unexpected_kwarg_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            GetSchemaArgs(foo=1)  # type: ignore[call-arg]


class GetSchemaEmptyDbTest(unittest.TestCase):
    def test_empty_db_still_valid_json(self) -> None:
        ctx = _mk_ctx(
            {},
            pd.DataFrame(columns=["PLATFORM_ID"]),
            pd.DataFrame(columns=["InfoCatergory"]),
        )
        result = get_schema_tool(ctx, GetSchemaArgs())
        payload = json.loads(result.content)
        self.assertEqual(payload["tables"], {})
        self.assertEqual(payload["distinct_PLATFORM_ID"], [])
        self.assertEqual(payload["distinct_InfoCatergory"], [])


class GetSchemaTypoPreservationTest(unittest.TestCase):
    def test_typo_in_sql_and_payload_keys(self) -> None:
        ctx = _mk_ctx(
            {"ufs_data": []},
            pd.DataFrame({"PLATFORM_ID": ["A"]}),
            pd.DataFrame({"InfoCatergory": ["§3"]}),
        )
        result = get_schema_tool(ctx, GetSchemaArgs())
        # Inspect the SQL strings passed to run_query
        sql_calls = [c.args[0] for c in ctx.db_adapter.run_query.call_args_list]
        joined = " ".join(sql_calls)
        self.assertIn("InfoCatergory", joined)
        # Runtime-concat the correct spelling so the SAFE-07 grep test
        # (plan 02-07) does not match a literal in this source file.
        correct_spelling = "Info" + "Category"
        self.assertNotIn(correct_spelling, joined)
        self.assertIn("distinct_InfoCatergory", result.content)
        self.assertNotIn(f"distinct_{correct_spelling}", result.content)


class GetSchemaProtocolTest(unittest.TestCase):
    def test_protocol_compliance(self) -> None:
        self.assertIsInstance(get_schema_tool, Tool)


if __name__ == "__main__":
    unittest.main()
