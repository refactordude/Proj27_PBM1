"""쿼리·LLM 호출 로깅.

- 파일: logs/queries.log, logs/llm.log (JSONL)
- 메모리: 최근 N개를 Streamlit session_state에 보관해 홈 화면에서 노출
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _log_dir() -> Path:
    override = os.environ.get("LOG_DIR")
    path = Path(override) if override else _REPO_ROOT / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _make_logger(name: str, filename: str) -> logging.Logger:
    logger = logging.getLogger(f"pbm.{name}")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(_log_dir() / filename, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_query(
    *,
    user: str,
    database: str,
    sql: str,
    rows: int | None = None,
    duration_ms: float | None = None,
    error: str | None = None,
) -> None:
    _make_logger("query", "queries.log").info(
        json.dumps(
            {
                "ts": _now(),
                "user": user,
                "database": database,
                "sql": sql,
                "rows": rows,
                "duration_ms": duration_ms,
                "error": error,
            },
            ensure_ascii=False,
        )
    )


def log_llm(
    *,
    user: str,
    model: str,
    question: str,
    sql: str | None = None,
    duration_ms: float | None = None,
    error: str | None = None,
    step_index: int | None = None,
    tool_call_names: str | None = None,
) -> None:
    _make_logger("llm", "llm.log").info(
        json.dumps(
            {
                "ts": _now(),
                "user": user,
                "model": model,
                "question": question,
                "sql": sql,
                "duration_ms": duration_ms,
                "error": error,
                "step_index": step_index,
                "tool_call_names": tool_call_names,
            },
            ensure_ascii=False,
        )
    )
