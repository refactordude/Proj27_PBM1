# Architecture

**Analysis Date:** 2026-04-22

## Pattern Overview

**Overall:** Layered adapter-based architecture with plugin-style database and LLM abstraction.

**Key Characteristics:**
- **Adapter pattern** decouples database and LLM implementations from the UI layer
- **Registry-based plugin system** allows runtime selection of adapters without code changes
- **Streamlit-centric UI** handles all presentation; state managed via `session_state` + YAML config
- **Safety-first SQL execution** validates queries before running against databases
- **Configuration-driven setup** uses YAML for database/LLM registration and user auth

## Layers

**Presentation / UI Layer:**
- Purpose: Streamlit pages and interactive components for user-facing features
- Location: `app/pages/` (home.py, explorer.py, compare.py, settings_page.py)
- Contains: Page logic, user input handling, result rendering, chat interfaces
- Depends on: `app.core.runtime` (resolver), `app.adapters.*` (via resolved instances)
- Used by: End users via Streamlit browser interface

**Core / Orchestration Layer:**
- Purpose: Runtime configuration resolution, session state management, authentication, logging, and SQL safety enforcement
- Location: `app/core/` (runtime.py, config.py, session.py, auth.py, logger.py, sql_safety.py)
- Contains: Settings loading/validation, DB/LLM adapter selection, user authentication, query/LLM logging, SQL validation
- Depends on: `app.adapters.db.base`, `app.adapters.llm.base`, Pydantic, Streamlit, YAML
- Used by: All pages, adapter factories

**Adapter / Integration Layer:**
- Purpose: Abstract database and LLM providers behind standardized interfaces
- Location: `app/adapters/` (db/, llm/)
- Contains: 
  - DB adapters: `base.py` (interface), `mysql.py` (MySQL impl), `registry.py` (factory)
  - LLM adapters: `base.py` (interface), `openai_adapter.py`, `ollama_adapter.py`, `registry.py` (factory)
- Depends on: SQLAlchemy + pymysql (DB), OpenAI SDK, pandas, sqlparse
- Used by: `app.core.runtime`, pages via resolved instances

**Utilities Layer:**
- Purpose: Helper functions for schema processing, data export, and visualization
- Location: `app/utils/` (schema.py, export.py, viz.py)
- Contains: Schema summarization for LLM context, CSV/Excel export, auto-chart generation
- Depends on: pandas, plotly
- Used by: Pages (home, explorer, compare)

**Configuration & Auth:**
- Purpose: Load and persist settings; manage user credentials
- Location: `config/settings.yaml`, `config/auth.yaml`
- Contains: Database connection details, LLM registration, app defaults, user accounts
- Depends on: YAML files on disk
- Used by: `app.core.config`, `app.core.auth`

## Data Flow

**Query Execution Flow (Explorer / Home AI Q&A):**

1. User enters natural language question or manual SQL in a page
2. Page calls `resolve_selected_db()` and `resolve_selected_llm()` from `app.core.runtime`
3. Runtime loads settings from YAML via `app.core.config.load_settings()`
4. Adapters are instantiated from registry based on config type
5. LLM adapter receives question + schema summary → generates SQL
6. SQL is extracted from LLM response via `app.utils.schema.extract_sql_from_response()`
7. SQL validation via `app.core.sql_safety.validate_and_sanitize()` → blocks writes, injects LIMIT
8. DB adapter executes sanitized SQL via `run_query()` → returns pandas DataFrame
9. Results are rendered; query is logged to `logs/queries.log`
10. Optional visualization via `app.utils.viz.auto_chart()`

**Configuration Update Flow (Settings Page):**

1. User submits new DB/LLM config in form
2. New config object added to `Settings` model in memory
3. `save_settings()` writes entire config to `config/settings.yaml`
4. `invalidate_settings()` clears cached settings in Streamlit
5. Next page load or reload triggers fresh `load_settings()` from disk
6. New adapters are built from updated config

**Authentication Flow:**

1. `require_login()` called in `app/main.py` before page rendering
2. Reads user credentials from `config/auth.yaml` via `streamlit_authenticator`
3. Validates input username/password against bcrypt hashes
4. On success: stores `user` in `session_state`; on failure: shows error and blocks page
5. Logout widget in sidebar updates auth status

**State Management:**

- **Transient (per-session)**: Chat history, recent queries, selected DB/LLM → stored in `st.session_state`
- **Persistent (per-app)**: DB connections, LLM configs → stored in YAML, loaded on startup
- **Authentication**: Cookie-based + bcrypt hashed credentials in YAML

## Key Abstractions

**DBAdapter:**
- Purpose: Uniform interface for database operations (query execution, schema inspection, connection testing)
- Examples: `app/adapters/db/base.py` (abstract), `app/adapters/db/mysql.py` (concrete)
- Pattern: Abstract base class with concrete implementations per database type; registry for factory lookup
- Methods: `test_connection()`, `list_tables()`, `get_schema()`, `run_query()`, `dispose()`

**LLMAdapter:**
- Purpose: Uniform interface for LLM operations (SQL generation from natural language, text streaming)
- Examples: `app/adapters/llm/base.py` (abstract), `app/adapters/llm/openai_adapter.py`, `app/adapters/llm/ollama_adapter.py`
- Pattern: Abstract base class with concrete implementations per LLM provider; registry for factory lookup
- Methods: `generate_sql()`, `stream_text()`
- Shared system prompt: `SQL_SYSTEM_PROMPT` in `base.py` defines rules for safe SQL generation

**Settings / DatabaseConfig / LLMConfig / AppConfig:**
- Purpose: Type-safe configuration models using Pydantic
- Examples: `app/core/config.py`
- Pattern: Pydantic `BaseModel` with Field defaults; persistent via `load_settings()` / `save_settings()`
- Fields: Connection details, API keys, temperature, row limits, default selections

**SafetyResult:**
- Purpose: Return type for SQL validation indicating success/failure + sanitized SQL
- Location: `app/core/sql_safety.py`
- Pattern: Dataclass with `ok` (bool), `reason` (str), `sanitized_sql` (str)

## Entry Points

**Main Application:**
- Location: `app/main.py`
- Triggers: `streamlit run app/main.py`
- Responsibilities: 
  - Sets page config (title "사내 데이터 플랫폼", wide layout)
  - Calls `require_login()` to enforce authentication
  - Loads settings and builds sidebar selectors
  - Builds Streamlit navigation via `st.navigation()` with pages
  - Routes to home/explorer/compare/settings pages

**Pages:**
- `app/pages/home.py` (F1): Dashboard with DB/LLM metrics, AI Q&A interface, chat history
- `app/pages/explorer.py` (F2): Table browser with filtering/sorting/pagination/export
- `app/pages/compare.py` (F3): Side-by-side query result comparison with diff highlighting
- `app/pages/settings_page.py` (F6): CRUD for DB/LLM configs, connection testing, app defaults

## Error Handling

**Strategy:** Graceful degradation with user-facing error messages; logging to files for debugging.

**Patterns:**

- **Adapter Loading Failures:** If DB/LLM adapter instantiation fails, `resolve_selected_db()` / `resolve_selected_llm()` return `(name, None, error_message)`. Pages check for `None` and display error.
- **Connection Errors:** Database connection failures caught in `MySQLAdapter.test_connection()` and `MySQLAdapter.run_query()` → errors displayed in UI; logged to `logs/queries.log` with error field.
- **SQL Validation Failures:** `validate_and_sanitize()` returns `SafetyResult(ok=False, reason="...")` → pages display reason and block execution.
- **Schema Load Failures:** Schema loading in pages wrapped in try/except; if fails, pages proceed with empty schema or cached schema.
- **LLM API Failures:** LLM calls wrapped in try/except; errors logged to `logs/llm.log` and displayed as `st.error()`.
- **Configuration Errors:** Missing or malformed YAML caught by Pydantic validation; defaults used where possible.

## Cross-Cutting Concerns

**Logging:**
- Framework: Python `logging` module (file-based)
- Approach: Two separate loggers: `pbm.query` (→ `logs/queries.log`) and `pbm.llm` (→ `logs/llm.log`)
- Format: JSON lines (JSONL) for easy parsing; includes timestamp (ISO 8601 UTC), user, operation details, duration, errors
- Functions: `log_query()` in `app/core/logger.py` (queries), `log_llm()` (LLM calls)

**Validation:**
- SQL: `app/core/sql_safety.validate_and_sanitize()` using regex + `sqlparse` library to block DDL/DML, enforce LIMIT
- Config: Pydantic models in `app/core/config.py` with type checking + field validators
- User Input: Streamlit UI widgets provide basic validation (e.g., port number range); forms check for duplicates

**Authentication:**
- Provider: `streamlit_authenticator` wrapper in `app/core/auth.py`
- Mechanism: Cookie-based session + bcrypt hashed credentials in `config/auth.yaml`
- Scope: Session-wide; username stored in `st.session_state["user"]` for logging

**Read-Only Enforcement:**
- Layer 1: SQL-level via `sql_safety.py` → blocks all non-SELECT statements
- Layer 2: DB-level via `MySQLAdapter.run_query()` → sets `SET SESSION TRANSACTION READ ONLY` if config has `readonly: true`
- Layer 3: Database user permissions → credentials should have `GRANT SELECT` only

---

*Architecture analysis: 2026-04-22*
