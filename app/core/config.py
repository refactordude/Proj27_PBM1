"""YAML 기반 설정 로드/저장.

Pydantic 모델로 타입 안전하게 파싱하고, 쓰기 시에는 원본 YAML 주석을 보존하지 않는
단순 dump 방식을 사용한다(MVP 단계이므로 충분).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from app.core.agent.config import AgentConfig

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SETTINGS_PATH = _REPO_ROOT / "config" / "settings.yaml"


class DatabaseConfig(BaseModel):
    name: str
    type: Literal["mysql", "postgres", "mssql", "bigquery", "snowflake"] = "mysql"
    host: str = "localhost"
    port: int = 3306
    database: str = ""
    user: str = ""
    password: str = ""
    readonly: bool = True


class LLMConfig(BaseModel):
    name: str
    type: Literal["openai", "anthropic", "ollama", "vllm", "custom"] = "openai"
    model: str = ""
    endpoint: str = ""
    api_key: str = ""
    temperature: float = 0.0
    max_tokens: int = 2000
    headers: dict[str, str] = Field(default_factory=dict)


class AppConfig(BaseModel):
    default_database: str = ""
    default_llm: str = ""
    query_row_limit: int = 1000
    recent_query_history: int = 20
    agent: AgentConfig = Field(default_factory=AgentConfig)


class Settings(BaseModel):
    databases: list[DatabaseConfig] = Field(default_factory=list)
    llms: list[LLMConfig] = Field(default_factory=list)
    app: AppConfig = Field(default_factory=AppConfig)


def _settings_path() -> Path:
    override = os.environ.get("SETTINGS_PATH")
    return Path(override) if override else _DEFAULT_SETTINGS_PATH


def load_settings() -> Settings:
    path = _settings_path()
    if not path.exists():
        return Settings()
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return Settings.model_validate(data)


def save_settings(settings: Settings) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            settings.model_dump(mode="python"),
            f,
            allow_unicode=True,
            sort_keys=False,
        )


def find_database(settings: Settings, name: str) -> DatabaseConfig | None:
    return next((d for d in settings.databases if d.name == name), None)


def find_llm(settings: Settings, name: str) -> LLMConfig | None:
    return next((m for m in settings.llms if m.name == name), None)
