from __future__ import annotations
import unittest

from app.core.agent.tools import TOOL_REGISTRY
from app.core.agent.tools._base import Tool


class ToolRegistryShapeTest(unittest.TestCase):
    CANONICAL_NAMES = {
        "run_sql",
        "get_schema",
        "pivot_to_wide",
        "normalize_result",
        "get_schema_docs",
        "make_chart",
    }

    def test_registry_has_exactly_six_entries(self):
        self.assertEqual(len(TOOL_REGISTRY), 6)

    def test_registry_has_all_canonical_names(self):
        self.assertEqual(set(TOOL_REGISTRY.keys()), self.CANONICAL_NAMES)

    def test_every_value_satisfies_tool_protocol(self):
        for name, tool in TOOL_REGISTRY.items():
            self.assertIsInstance(tool, Tool, f"{name} does not satisfy Tool Protocol")

    # Tools with at least one argument — must emit non-empty properties.
    # get_schema is intentionally a no-arg tool (properties: {}) — still OpenAI-compatible
    # but excluded from the non-empty-properties check.
    _NO_ARG_TOOLS = {"get_schema"}

    def test_every_args_model_produces_openai_compatible_schema(self):
        for name, tool in TOOL_REGISTRY.items():
            schema = tool.args_model.model_json_schema()
            self.assertEqual(schema.get("type"), "object", f"{name} schema type != object")
            self.assertIn("properties", schema, f"{name} schema missing properties")
            self.assertIsInstance(
                schema["properties"], dict, f"{name} properties is not a dict"
            )
            if name not in self._NO_ARG_TOOLS:
                self.assertGreater(
                    len(schema["properties"]), 0, f"{name} schema has empty properties"
                )

    def test_no_duplicate_names(self):
        names = [t.name for t in TOOL_REGISTRY.values()]
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
