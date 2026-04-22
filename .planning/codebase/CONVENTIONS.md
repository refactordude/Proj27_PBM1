# Coding Conventions

**Analysis Date:** 2026-04-22

## Naming Patterns

**Files:**
- Module files use `snake_case`: `config.py`, `sql_safety.py`, `openai_adapter.py`
- Adapter implementations suffix with `_adapter.py`: `openai_adapter.py`, `ollama_adapter.py`
- Registry files named `registry.py` for adapter lookup tables
- Page/UI files match feature name: `home.py`, `explorer.py`, `compare.py`, `settings_page.py`

**Functions:**
- Use `snake_case` for all function names
- Private functions prefix with `_`: `_make_logger()`, `_get_engine()`, `_load_settings_cached()`
- Functions returning tuples use descriptive names: `test_connection()` returns `(bool, str)`
- Functions returning checked results use dedicated return types: `SafetyResult` dataclass in `sql_safety.py`

**Variables:**
- Use `snake_case`: `table_name`, `default_limit`, `schema_text`, `start`, `duration_ms`
- Private module-level constants use `_UPPERCASE`: `_REPO_ROOT`, `_CHAT_HISTORY_KEY`, `_FORBIDDEN` (regex pattern)
- Public configuration constants: `ALLOWED_STATEMENT_TYPES = {"SELECT"}`
- Dictionary keys use `snake_case`: `"sanitized_sql"`, `"duration_ms"`

**Types:**
- Use `PascalCase` for classes: `DatabaseConfig`, `LLMConfig`, `MySQLAdapter`, `SafetyResult`
- Use `PascalCase` for Pydantic models: `AppConfig`, `Settings`
- Enum-like constants use `_UPPERCASE` for private: `_ALLOWED_STATEMENT_TYPES`, `_ALLOWED_LEADING_KEYWORDS`

## Code Style

**Formatting:**
- No explicit formatter configured (Ruff/Black not detected)
- Imports use `from __future__ import annotations` at module top (Python 3.10+ annotation style)
- Lines observed typically 80-100 characters
- 4-space indentation consistently used
- Comments on separate lines above code, not inline

**Linting:**
- No linting config file present (`pylintrc`, `.flake8`, `ruff.toml` not found)
- Code follows implicit PEP 8 style conventions
- Comment markers like `# pragma: no cover` used for test coverage exclusion

## Import Organization

**Order:**
1. `from __future__ import annotations` (always first)
2. Standard library imports: `import sys`, `from pathlib import Path`, `from typing import Literal`
3. Third-party imports: `import streamlit as st`, `from pydantic import BaseModel`, `from sqlalchemy import create_engine`
4. Local app imports: `from app.core.config import Settings`, `from app.adapters.db.base import DBAdapter`
5. Conditional delayed imports for Streamlit (marked with `# noqa: E402` after delayed import comment explaining why)

**Path Aliases:**
- No alias paths detected (uses absolute imports from `app.*`)
- Imports always use absolute paths starting from `app/` package root

**Example pattern from `app/main.py`:**
```python
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

# [Path setup code]

import streamlit as st  # noqa: E402

from app.core.auth import require_login  # noqa: E402
from app.core.runtime import settings, sidebar_selectors  # noqa: E402
```

## Error Handling

**Patterns:**
- Broad `except Exception` catching with error logging via dedicated functions
- Errors logged to JSONL files with `log_query()` and `log_llm()` for audit trail
- User-facing errors passed through Streamlit UI: `st.error()`, `st.warning()`, `st.info()`
- Critical failures use `st.stop()` to halt page rendering

**Example from `app/pages/home.py` (lines 74-97):**
```python
try:
    raw = llm_adapter.generate_sql(
        question=question,
        schema_summary=schema_text,
        history=[h for h in get_chat_history() if h["role"] in {"user", "assistant"}],
    )
    duration = (time.perf_counter() - start) * 1000
    sql_only = extract_sql_from_response(raw)
    log_llm(
        user=st.session_state.get("user", "unknown"),
        model=llm_name or "",
        question=question,
        sql=sql_only,
        duration_ms=duration,
    )
except Exception as exc:
    log_llm(
        user=st.session_state.get("user", "unknown"),
        model=llm_name or "",
        question=question,
        error=str(exc),
    )
    st.error(f"LLM 호출 실패: {exc}")
    st.stop()
```

**Result types for complex returns:**
- Use dataclasses for multi-value returns: `SafetyResult(ok=bool, reason=str, sanitized_sql=str)` in `sql_safety.py`
- Tuples for simple pairs: `(bool, str)` for connection test results

## Logging

**Framework:** Python's standard `logging` module (configured in `app/core/logger.py`)

**Patterns:**
- Structured logging via JSONL files (one JSON object per line)
- Two log files: `logs/queries.log` and `logs/llm.log`
- Logs include ISO timestamp: `"ts": _now()` (UTC timezone)
- All function calls use keyword-only arguments for clarity

**Example from `app/core/logger.py` (lines 40-62):**
```python
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
```

## Comments

**When to Comment:**
- Module docstrings describe purpose, context, and technical decisions: `"""YAML 기반 설정 로드/저장. Pydantic 모델로 타입 안전하게..."""`
- Function docstrings for complex behavior: See `require_login()` in `app/core/auth.py`
- Inline comments explain why, not what: `# 일부 버전/권한에서 실패할 수 있음; sql_safety가 1차 방어`
- Comments in Korean (project language)

**JSDoc/TSDoc:**
- Not used (Python project, not TypeScript)
- Pydantic model fields use `Field()` with descriptions when needed: `Field(default_factory=list)`

## Function Design

**Size:** Functions typically 15-50 lines; longer functions break into private helpers

**Parameters:**
- Use keyword-only parameters for clarity in public APIs: `def log_query(*, user: str, database: str, ...)`
- Optional parameters with defaults after required: `def summarize(schema: dict[...], *, max_tables: int = 40, max_cols: int = 30)`
- Type hints always present (Python 3.10+): `def run_query(self, sql: str) -> pd.DataFrame:`

**Return Values:**
- Explicit return type annotations: `-> str`, `-> tuple[bool, str]`, `-> SafetyResult`
- Return `None` explicitly for void functions: `-> None`
- Complex returns use dataclasses or named tuples over bare tuples

**Example from `app/adapters/db/base.py`:**
```python
@abstractmethod
def test_connection(self) -> tuple[bool, str]:
    """(성공 여부, 메시지)"""

@abstractmethod
def get_schema(self, tables: list[str] | None = None) -> dict[str, list[dict]]:
    """table_name -> list of {name, type, nullable, pk} 컬럼 정보"""
```

## Module Design

**Exports:**
- No `__all__` declarations observed; all public names are module-level functions and classes
- Private names prefixed with `_` to indicate internal-only usage
- Modules typically export 2-5 public functions/classes

**Barrel Files:**
- Minimal use: `app/__init__.py`, `app/core/__init__.py`, `app/adapters/__init__.py` are empty or minimal
- Imports are explicit to avoid circular dependencies: `from app.core.config import Settings`

**File organization:**
- Base interfaces in `**/base.py`: `app/adapters/db/base.py`, `app/adapters/llm/base.py`
- Concrete implementations in named modules: `app/adapters/db/mysql.py`, `app/adapters/llm/openai_adapter.py`
- Registry patterns in `registry.py`: Keeps adapter type → class mapping centralized
- Utilities organized by domain: `app/utils/schema.py`, `app/utils/export.py`, `app/utils/viz.py`

---

*Convention analysis: 2026-04-22*
