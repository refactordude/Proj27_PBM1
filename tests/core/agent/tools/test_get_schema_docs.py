"""get_schema_docs 도구 단위 테스트 (TEST-01 for TOOL-05)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from app.core.agent.tools.get_schema_docs import (
    GetSchemaDocsArgs,
    _SPEC_DOCS,
    get_schema_docs_tool,
)


class GetSchemaDocsHappyPathTest(unittest.TestCase):
    """Happy path: section 3 returns the scaffold text with §3 header."""

    def test_section_3_returns_scaffold_text(self) -> None:
        ctx = MagicMock()
        result = get_schema_docs_tool(ctx, GetSchemaDocsArgs(section=3))
        self.assertIn("§3", result.content)
        self.assertNotIn("not yet authored", result.content)

    def test_tool_has_name_and_args_model(self) -> None:
        self.assertEqual(get_schema_docs_tool.name, "get_schema_docs")
        self.assertIs(get_schema_docs_tool.args_model, GetSchemaDocsArgs)


class GetSchemaDocsArgValidationTest(unittest.TestCase):
    """Pydantic bounds: section must be in [1, 7]."""

    def test_section_zero_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            GetSchemaDocsArgs(section=0)

    def test_section_eight_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            GetSchemaDocsArgs(section=8)


class GetSchemaDocsMissingFileTest(unittest.TestCase):
    """Edge case: missing file path resolves to fallback text."""

    def test_missing_file_returns_fallback_text(self) -> None:
        ctx = MagicMock()
        # patch the module-level dict to simulate a missing file
        with patch.dict(
            _SPEC_DOCS,
            {5: "(section_5.txt missing — not yet authored)"},
        ):
            result = get_schema_docs_tool(ctx, GetSchemaDocsArgs(section=5))
            self.assertIn("missing", result.content)


if __name__ == "__main__":
    unittest.main()
