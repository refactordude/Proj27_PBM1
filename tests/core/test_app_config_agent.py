"""AppConfig.agent 구성 및 YAML 라운드트립 검증 (OBS-03, Pattern 4)."""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

import yaml

from app.core.agent.config import AgentConfig
from app.core.config import AppConfig, Settings, load_settings, save_settings


class AppConfigAgentFieldTest(unittest.TestCase):
    def test_app_config_has_agent_default(self) -> None:
        app_cfg = AppConfig()
        self.assertIsInstance(app_cfg.agent, AgentConfig)
        self.assertEqual(app_cfg.agent.model, "gpt-4.1-mini")
        self.assertEqual(app_cfg.agent.max_steps, 5)
        self.assertEqual(app_cfg.agent.row_cap, 200)
        self.assertEqual(app_cfg.agent.timeout_s, 30)
        self.assertEqual(app_cfg.agent.allowed_tables, ["ufs_data"])
        self.assertEqual(app_cfg.agent.max_context_tokens, 30_000)

    def test_each_instance_has_distinct_agent_allowed_tables(self) -> None:
        a = AppConfig()
        b = AppConfig()
        a.agent.allowed_tables.append("other")
        self.assertEqual(b.agent.allowed_tables, ["ufs_data"])


class SettingsYamlRoundTripTest(unittest.TestCase):
    def test_full_round_trip(self) -> None:
        s = Settings()
        dumped = yaml.safe_dump(
            s.model_dump(mode="python"), allow_unicode=True, sort_keys=False
        )
        restored = Settings.model_validate(yaml.safe_load(dumped))
        self.assertEqual(restored, s)

    def test_load_yaml_without_agent_block_falls_back_to_defaults(self) -> None:
        """Backward compatibility: old settings.yaml has no app.agent."""
        minimal = {
            "databases": [],
            "llms": [],
            "app": {
                "default_database": "X",
                "default_llm": "Y",
                "query_row_limit": 500,
                "recent_query_history": 10,
                # NOTE: no 'agent' key
            },
        }
        s = Settings.model_validate(minimal)
        self.assertEqual(s.app.agent.model, "gpt-4.1-mini")
        self.assertEqual(s.app.agent.max_steps, 5)
        self.assertEqual(s.app.agent.allowed_tables, ["ufs_data"])


class SettingsDiskRoundTripTest(unittest.TestCase):
    """Write Settings() to a temp path via save_settings, reload via load_settings."""

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self._path = Path(self._tmp.name) / "settings.yaml"
        self._prev_env = os.environ.get("SETTINGS_PATH")
        os.environ["SETTINGS_PATH"] = str(self._path)

    def tearDown(self) -> None:
        if self._prev_env is None:
            os.environ.pop("SETTINGS_PATH", None)
        else:
            os.environ["SETTINGS_PATH"] = self._prev_env
        self._tmp.cleanup()

    def test_save_then_load_preserves_agent(self) -> None:
        original = Settings()
        save_settings(original)
        self.assertTrue(self._path.exists())
        loaded = load_settings()
        self.assertEqual(loaded.app.agent.model, "gpt-4.1-mini")
        self.assertEqual(loaded.app.agent.allowed_tables, ["ufs_data"])
        self.assertEqual(loaded.app.agent.max_context_tokens, 30_000)

    def test_load_old_yaml_without_agent_block(self) -> None:
        """Simulate an operator's pre-Phase-1 settings.yaml."""
        self._path.write_text(
            "databases: []\n"
            "llms: []\n"
            "app:\n"
            "  default_database: 'legacy'\n"
            "  default_llm: 'legacy-llm'\n"
            "  query_row_limit: 777\n"
            "  recent_query_history: 12\n",
            encoding="utf-8",
        )
        loaded = load_settings()
        self.assertEqual(loaded.app.default_database, "legacy")
        self.assertEqual(loaded.app.query_row_limit, 777)
        # The new agent block defaults in:
        self.assertEqual(loaded.app.agent.model, "gpt-4.1-mini")
        self.assertEqual(loaded.app.agent.max_steps, 5)


if __name__ == "__main__":
    unittest.main()
