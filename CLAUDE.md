<!-- GSD:project-start source:PROJECT.md -->
## Project

**Internal Data Platform — Agentic UFS Q&A**

A Streamlit-based internal data platform for querying a MySQL database of UFS (Universal Flash Storage) device benchmark profiles. The current milestone replaces the existing "generate-SQL-and-confirm" NL interface on Home with an **agentic LLM engine** that autonomously runs SELECT queries against the UFS dataset, inspects results, iterates, and returns a streamed answer plus an LLM-chosen Plotly chart.

**Core Value:** Ask a UFS question in plain language and get a correct, visualized answer — without manually writing or confirming SQL — on a safety-bounded read-only loop over the UFS benchmarking database.

### Constraints

- **Tech stack**: Python 3.11 + Streamlit 1.40+ + SQLAlchemy 2.0 + pymysql + Plotly + Pydantic 2 + OpenAI SDK 1.50+ — the agentic engine must fit this stack without adding new frameworks.
- **Provider**: OpenAI-only for the agentic loop in v1 (`chat.completions` with `tools=[...]`, tool-capable model required — gpt-4o / gpt-4o-mini).
- **Database**: MySQL read-only; single table `ufs_data` is the only allowed target of `run_sql` in v1.
- **Safety**: SELECT-only + auto-LIMIT + table allowlist + `max_steps=5` per turn are non-negotiable; any change to these requires explicit approval.
- **Deployment**: Must continue to run via `streamlit run app/main.py` and `docker compose up` without new services.
- **Auth**: Behind existing `streamlit-authenticator` login — no new auth surface.
- **Compatibility**: Explorer / Compare / Settings pages must function unchanged after Home is rewritten.
- **Budget**: Hard per-turn ceiling — `max_steps=5`, `row_cap=200`, `timeout_s=30` — configurable in `AppConfig` but defaults are conservative.
- **Dependencies added** (expected): none required beyond what's already in `requirements.txt`; OpenAI SDK 1.50+ already supports tools.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.11 - Web application, data processing, LLM adapters
## Runtime
- Python 3.11-slim (Docker base image)
- pip (dependency management)
- Lockfile: `requirements.txt` (pinned versions present)
## Frameworks
- Streamlit 1.40+ - Web UI framework for data platform
- streamlit-authenticator 0.3.3+ - User authentication and session management
- SQLAlchemy 2.0+ - ORM and database abstraction layer
- pymysql 1.1+ - MySQL driver for SQLAlchemy
- pandas 2.2+ - DataFrame operations for query results
- openpyxl 3.1+ - Excel file export support
- openai 1.50+ - OpenAI API client (GPT-4o, GPT-4o-mini)
- requests 2.32+ - HTTP client for Ollama and other HTTP-based APIs
- Plotly 5.22+ - Interactive charting and visualization
- Altair 5.3+ - Declarative charting library
- Pydantic 2.7+ - Data validation and settings management
- PyYAML 6.0+ - YAML configuration file parsing
- python-dotenv 1.0+ - Environment variable loading from .env
- bcrypt 4.2+ - Password hashing for authentication
- sqlparse 0.5+ - SQL parsing and validation
## Key Dependencies
- openai 1.50+ - Required for main AI query generation via OpenAI API
- streamlit 1.40+ - Core UI framework
- SQLAlchemy 2.0+ - Database abstraction for multi-database support
- pymysql 1.1+ - MySQL connectivity
- requests 2.32+ - HTTP requests for Ollama and external APIs
- pandas 2.2+ - Data manipulation and export
## Configuration
- Loaded via `python-dotenv` from `.env` file (see `.env.example`)
- Path override: `SETTINGS_PATH` environment variable
- Auth override: `AUTH_PATH` environment variable
- Log override: `LOG_DIR` environment variable
- `OPENAI_API_KEY` - OpenAI API key (can be set in environment or settings UI)
- `config/settings.yaml` - Database and LLM configuration (auto-managed via Settings UI)
- `config/auth.yaml` - User credentials and authentication settings
- `Dockerfile` - Multi-stage build with Python 3.11-slim base
- `docker-compose.yml` - Service orchestration (app service configured, MySQL service optional/commented)
## Platform Requirements
- Python 3.11+
- pip package manager
- Git (for version control)
- Docker (containerized deployment)
- Python 3.11 runtime
- MySQL 8.0+ (or supported alternative database)
- Network access to OpenAI API (if using OpenAI models)
- Optionally: Ollama for local LLM support
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Module files use `snake_case`: `config.py`, `sql_safety.py`, `openai_adapter.py`
- Adapter implementations suffix with `_adapter.py`: `openai_adapter.py`, `ollama_adapter.py`
- Registry files named `registry.py` for adapter lookup tables
- Page/UI files match feature name: `home.py`, `explorer.py`, `compare.py`, `settings_page.py`
- Use `snake_case` for all function names
- Private functions prefix with `_`: `_make_logger()`, `_get_engine()`, `_load_settings_cached()`
- Functions returning tuples use descriptive names: `test_connection()` returns `(bool, str)`
- Functions returning checked results use dedicated return types: `SafetyResult` dataclass in `sql_safety.py`
- Use `snake_case`: `table_name`, `default_limit`, `schema_text`, `start`, `duration_ms`
- Private module-level constants use `_UPPERCASE`: `_REPO_ROOT`, `_CHAT_HISTORY_KEY`, `_FORBIDDEN` (regex pattern)
- Public configuration constants: `ALLOWED_STATEMENT_TYPES = {"SELECT"}`
- Dictionary keys use `snake_case`: `"sanitized_sql"`, `"duration_ms"`
- Use `PascalCase` for classes: `DatabaseConfig`, `LLMConfig`, `MySQLAdapter`, `SafetyResult`
- Use `PascalCase` for Pydantic models: `AppConfig`, `Settings`
- Enum-like constants use `_UPPERCASE` for private: `_ALLOWED_STATEMENT_TYPES`, `_ALLOWED_LEADING_KEYWORDS`
## Code Style
- No explicit formatter configured (Ruff/Black not detected)
- Imports use `from __future__ import annotations` at module top (Python 3.10+ annotation style)
- Lines observed typically 80-100 characters
- 4-space indentation consistently used
- Comments on separate lines above code, not inline
- No linting config file present (`pylintrc`, `.flake8`, `ruff.toml` not found)
- Code follows implicit PEP 8 style conventions
- Comment markers like `# pragma: no cover` used for test coverage exclusion
## Import Organization
- No alias paths detected (uses absolute imports from `app.*`)
- Imports always use absolute paths starting from `app/` package root
## Error Handling
- Broad `except Exception` catching with error logging via dedicated functions
- Errors logged to JSONL files with `log_query()` and `log_llm()` for audit trail
- User-facing errors passed through Streamlit UI: `st.error()`, `st.warning()`, `st.info()`
- Critical failures use `st.stop()` to halt page rendering
- Use dataclasses for multi-value returns: `SafetyResult(ok=bool, reason=str, sanitized_sql=str)` in `sql_safety.py`
- Tuples for simple pairs: `(bool, str)` for connection test results
## Logging
- Structured logging via JSONL files (one JSON object per line)
- Two log files: `logs/queries.log` and `logs/llm.log`
- Logs include ISO timestamp: `"ts": _now()` (UTC timezone)
- All function calls use keyword-only arguments for clarity
## Comments
- Module docstrings describe purpose, context, and technical decisions: `"""YAML 기반 설정 로드/저장. Pydantic 모델로 타입 안전하게..."""`
- Function docstrings for complex behavior: See `require_login()` in `app/core/auth.py`
- Inline comments explain why, not what: `# 일부 버전/권한에서 실패할 수 있음; sql_safety가 1차 방어`
- Comments in Korean (project language)
- Not used (Python project, not TypeScript)
- Pydantic model fields use `Field()` with descriptions when needed: `Field(default_factory=list)`
## Function Design
- Use keyword-only parameters for clarity in public APIs: `def log_query(*, user: str, database: str, ...)`
- Optional parameters with defaults after required: `def summarize(schema: dict[...], *, max_tables: int = 40, max_cols: int = 30)`
- Type hints always present (Python 3.10+): `def run_query(self, sql: str) -> pd.DataFrame:`
- Explicit return type annotations: `-> str`, `-> tuple[bool, str]`, `-> SafetyResult`
- Return `None` explicitly for void functions: `-> None`
- Complex returns use dataclasses or named tuples over bare tuples
## Module Design
- No `__all__` declarations observed; all public names are module-level functions and classes
- Private names prefixed with `_` to indicate internal-only usage
- Modules typically export 2-5 public functions/classes
- Minimal use: `app/__init__.py`, `app/core/__init__.py`, `app/adapters/__init__.py` are empty or minimal
- Imports are explicit to avoid circular dependencies: `from app.core.config import Settings`
- Base interfaces in `**/base.py`: `app/adapters/db/base.py`, `app/adapters/llm/base.py`
- Concrete implementations in named modules: `app/adapters/db/mysql.py`, `app/adapters/llm/openai_adapter.py`
- Registry patterns in `registry.py`: Keeps adapter type → class mapping centralized
- Utilities organized by domain: `app/utils/schema.py`, `app/utils/export.py`, `app/utils/viz.py`
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- **Adapter pattern** decouples database and LLM implementations from the UI layer
- **Registry-based plugin system** allows runtime selection of adapters without code changes
- **Streamlit-centric UI** handles all presentation; state managed via `session_state` + YAML config
- **Safety-first SQL execution** validates queries before running against databases
- **Configuration-driven setup** uses YAML for database/LLM registration and user auth
## Layers
- Purpose: Streamlit pages and interactive components for user-facing features
- Location: `app/pages/` (home.py, explorer.py, compare.py, settings_page.py)
- Contains: Page logic, user input handling, result rendering, chat interfaces
- Depends on: `app.core.runtime` (resolver), `app.adapters.*` (via resolved instances)
- Used by: End users via Streamlit browser interface
- Purpose: Runtime configuration resolution, session state management, authentication, logging, and SQL safety enforcement
- Location: `app/core/` (runtime.py, config.py, session.py, auth.py, logger.py, sql_safety.py)
- Contains: Settings loading/validation, DB/LLM adapter selection, user authentication, query/LLM logging, SQL validation
- Depends on: `app.adapters.db.base`, `app.adapters.llm.base`, Pydantic, Streamlit, YAML
- Used by: All pages, adapter factories
- Purpose: Abstract database and LLM providers behind standardized interfaces
- Location: `app/adapters/` (db/, llm/)
- Contains: 
- Depends on: SQLAlchemy + pymysql (DB), OpenAI SDK, pandas, sqlparse
- Used by: `app.core.runtime`, pages via resolved instances
- Purpose: Helper functions for schema processing, data export, and visualization
- Location: `app/utils/` (schema.py, export.py, viz.py)
- Contains: Schema summarization for LLM context, CSV/Excel export, auto-chart generation
- Depends on: pandas, plotly
- Used by: Pages (home, explorer, compare)
- Purpose: Load and persist settings; manage user credentials
- Location: `config/settings.yaml`, `config/auth.yaml`
- Contains: Database connection details, LLM registration, app defaults, user accounts
- Depends on: YAML files on disk
- Used by: `app.core.config`, `app.core.auth`
## Data Flow
- **Transient (per-session)**: Chat history, recent queries, selected DB/LLM → stored in `st.session_state`
- **Persistent (per-app)**: DB connections, LLM configs → stored in YAML, loaded on startup
- **Authentication**: Cookie-based + bcrypt hashed credentials in YAML
## Key Abstractions
- Purpose: Uniform interface for database operations (query execution, schema inspection, connection testing)
- Examples: `app/adapters/db/base.py` (abstract), `app/adapters/db/mysql.py` (concrete)
- Pattern: Abstract base class with concrete implementations per database type; registry for factory lookup
- Methods: `test_connection()`, `list_tables()`, `get_schema()`, `run_query()`, `dispose()`
- Purpose: Uniform interface for LLM operations (SQL generation from natural language, text streaming)
- Examples: `app/adapters/llm/base.py` (abstract), `app/adapters/llm/openai_adapter.py`, `app/adapters/llm/ollama_adapter.py`
- Pattern: Abstract base class with concrete implementations per LLM provider; registry for factory lookup
- Methods: `generate_sql()`, `stream_text()`
- Shared system prompt: `SQL_SYSTEM_PROMPT` in `base.py` defines rules for safe SQL generation
- Purpose: Type-safe configuration models using Pydantic
- Examples: `app/core/config.py`
- Pattern: Pydantic `BaseModel` with Field defaults; persistent via `load_settings()` / `save_settings()`
- Fields: Connection details, API keys, temperature, row limits, default selections
- Purpose: Return type for SQL validation indicating success/failure + sanitized SQL
- Location: `app/core/sql_safety.py`
- Pattern: Dataclass with `ok` (bool), `reason` (str), `sanitized_sql` (str)
## Entry Points
- Location: `app/main.py`
- Triggers: `streamlit run app/main.py`
- Responsibilities: 
- `app/pages/home.py` (F1): Dashboard with DB/LLM metrics, AI Q&A interface, chat history
- `app/pages/explorer.py` (F2): Table browser with filtering/sorting/pagination/export
- `app/pages/compare.py` (F3): Side-by-side query result comparison with diff highlighting
- `app/pages/settings_page.py` (F6): CRUD for DB/LLM configs, connection testing, app defaults
## Error Handling
- **Adapter Loading Failures:** If DB/LLM adapter instantiation fails, `resolve_selected_db()` / `resolve_selected_llm()` return `(name, None, error_message)`. Pages check for `None` and display error.
- **Connection Errors:** Database connection failures caught in `MySQLAdapter.test_connection()` and `MySQLAdapter.run_query()` → errors displayed in UI; logged to `logs/queries.log` with error field.
- **SQL Validation Failures:** `validate_and_sanitize()` returns `SafetyResult(ok=False, reason="...")` → pages display reason and block execution.
- **Schema Load Failures:** Schema loading in pages wrapped in try/except; if fails, pages proceed with empty schema or cached schema.
- **LLM API Failures:** LLM calls wrapped in try/except; errors logged to `logs/llm.log` and displayed as `st.error()`.
- **Configuration Errors:** Missing or malformed YAML caught by Pydantic validation; defaults used where possible.
## Cross-Cutting Concerns
- Framework: Python `logging` module (file-based)
- Approach: Two separate loggers: `pbm.query` (→ `logs/queries.log`) and `pbm.llm` (→ `logs/llm.log`)
- Format: JSON lines (JSONL) for easy parsing; includes timestamp (ISO 8601 UTC), user, operation details, duration, errors
- Functions: `log_query()` in `app/core/logger.py` (queries), `log_llm()` (LLM calls)
- SQL: `app/core/sql_safety.validate_and_sanitize()` using regex + `sqlparse` library to block DDL/DML, enforce LIMIT
- Config: Pydantic models in `app/core/config.py` with type checking + field validators
- User Input: Streamlit UI widgets provide basic validation (e.g., port number range); forms check for duplicates
- Provider: `streamlit_authenticator` wrapper in `app/core/auth.py`
- Mechanism: Cookie-based session + bcrypt hashed credentials in `config/auth.yaml`
- Scope: Session-wide; username stored in `st.session_state["user"]` for logging
- Layer 1: SQL-level via `sql_safety.py` → blocks all non-SELECT statements
- Layer 2: DB-level via `MySQLAdapter.run_query()` → sets `SET SESSION TRANSACTION READ ONLY` if config has `readonly: true`
- Layer 3: Database user permissions → credentials should have `GRANT SELECT` only
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
