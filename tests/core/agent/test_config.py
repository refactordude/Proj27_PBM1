"""AgentConfig 필드 기본값, 바운드, YAML 라운드트립 검증 (SC1, OBS-03, AGENT-09)."""
from __future__ import annotations

import unittest

import yaml
from pydantic import ValidationError

from app.core.agent.config import AgentConfig


class AgentConfigDefaultsTest(unittest.TestCase):
    def test_defaults(self) -> None:
        c = AgentConfig()
        # Empty default means "fall back to selected LLM's model" (see
        # app.core.agent.loop._resolve_model). AGENT-09 override path kept
        # alive by allowing operators to set a non-empty string.
        self.assertEqual(c.model, "")
        self.assertEqual(c.max_steps, 5)
        self.assertEqual(c.row_cap, 200)
        self.assertEqual(c.timeout_s, 30)
        self.assertEqual(c.allowed_tables, ["ufs_data"])
        self.assertEqual(c.max_context_tokens, 30_000)

    def test_model_dump_roundtrip(self) -> None:
        c = AgentConfig()
        dumped = c.model_dump()
        self.assertEqual(
            dumped,
            {
                "model": "",
                "max_steps": 5,
                "row_cap": 200,
                "timeout_s": 30,
                "allowed_tables": ["ufs_data"],
                "max_context_tokens": 30_000,
            },
        )
        text = yaml.safe_dump(dumped)
        restored = AgentConfig.model_validate(yaml.safe_load(text))
        self.assertEqual(restored, c)


class AgentConfigBoundsTest(unittest.TestCase):
    def test_max_steps_too_low(self) -> None:
        with self.assertRaises(ValidationError):
            AgentConfig(max_steps=0)

    def test_max_steps_too_high(self) -> None:
        with self.assertRaises(ValidationError):
            AgentConfig(max_steps=21)

    def test_timeout_too_low(self) -> None:
        with self.assertRaises(ValidationError):
            AgentConfig(timeout_s=2)

    def test_timeout_too_high(self) -> None:
        with self.assertRaises(ValidationError):
            AgentConfig(timeout_s=400)

    def test_row_cap_too_low(self) -> None:
        with self.assertRaises(ValidationError):
            AgentConfig(row_cap=0)

    def test_max_context_tokens_too_low(self) -> None:
        with self.assertRaises(ValidationError):
            AgentConfig(max_context_tokens=500)


class AgentConfigInstanceIndependenceTest(unittest.TestCase):
    def test_allowed_tables_is_instance_level(self) -> None:
        """Two AgentConfig instances have independent allowed_tables lists."""
        c1 = AgentConfig()
        c2 = AgentConfig()
        c1.allowed_tables.append("other_table")
        self.assertEqual(c2.allowed_tables, ["ufs_data"])


if __name__ == "__main__":
    unittest.main()
