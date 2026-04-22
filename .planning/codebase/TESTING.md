# Testing Patterns

**Analysis Date:** 2026-04-22

## Test Framework Status

**IMPORTANT: No automated tests currently exist in this codebase.**

**Test Framework:**
- Not configured
- No test files found: `tests/`, `test_*.py`, `*_test.py` do not exist
- No test configuration: `pytest.ini`, `pyproject.toml` with `[tool.pytest]`, `setup.cfg`, `tox.ini` not present

**Assertion Library:**
- Not applicable (no tests present)

**Run Commands:**
- No test runner configured
- To add tests: Would need to install `pytest` and create test structure

## Testing Gaps

The codebase currently lacks automated test coverage. This creates risk for:

1. **Database Adapter Logic** (`app/adapters/db/`)
   - MySQL connection pooling and read-only transaction enforcement
   - Schema extraction and column type parsing
   - Query execution and DataFrame conversion
   - Error handling for missing tables/columns

2. **LLM Integration** (`app/adapters/llm/`)
   - OpenAI API calls with custom headers
   - Message formatting and history management
   - Streaming response handling
   - Error handling for API failures

3. **SQL Safety Validation** (`app/core/sql_safety.py`)
   - Keyword blacklist enforcement (INSERT, UPDATE, DELETE, etc.)
   - LIMIT clause auto-injection
   - Multi-statement detection
   - Edge cases in SQL parsing

4. **Configuration Loading** (`app/core/config.py`)
   - YAML parsing and Pydantic validation
   - Settings file not found behavior
   - Type coercion for database configs

5. **Session State Management** (`app/core/session.py`)
   - Chat history append/reset
   - Recent query recording with max_items limit
   - Database and LLM selection persistence

6. **Logging** (`app/core/logger.py`)
   - JSONL file writing and formatting
   - Timestamp generation and ISO format
   - Log directory creation and permissions

## Test File Organization

**Current Structure:**
```
/home/yh/Desktop/02_Projects/Proj27_PBM1/
├── app/
│   ├── adapters/
│   ├── core/
│   ├── pages/
│   └── utils/
└── [NO tests/ directory]
```

**Recommended Structure for Tests:**
```
tests/
├── conftest.py                    # Pytest fixtures
├── test_core/
│   ├── test_config.py
│   ├── test_sql_safety.py
│   ├── test_auth.py
│   └── test_logger.py
├── test_adapters/
│   ├── test_db_mysql.py
│   ├── test_llm_openai.py
│   └── test_llm_ollama.py
├── test_utils/
│   ├── test_schema.py
│   ├── test_export.py
│   └── test_viz.py
└── test_pages/
    ├── test_home.py
    └── test_explorer.py
```

**Location:** Test files should be co-located in a `tests/` directory at project root (separate from `app/`)

## What Needs Testing

### Priority 1: Core Safety & Data Integrity

**1. SQL Safety Validation** (`app/core/sql_safety.py`)
```python
# Test cases needed:
# - validate_and_sanitize() allows SELECT/WITH/SHOW/DESCRIBE/EXPLAIN
# - Rejects INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/GRANT/REVOKE
# - Handles multiple statements (separated by ;) as error
# - Auto-injects LIMIT when missing from SELECT
# - Handles edge cases: empty SQL, only comments, malformed syntax
# - Preserves original SQL when validation passes
```

**2. Database Connection** (`app/adapters/db/mysql.py`)
```python
# Test cases needed:
# - test_connection() returns (True, message) on success
# - test_connection() returns (False, error) on invalid credentials
# - Schema extraction parses primary keys correctly
# - Query execution returns pandas DataFrame
# - Read-only mode enforces "SET SESSION TRANSACTION READ ONLY"
# - Connection pooling reuses engine (lazy initialization)
```

**3. Configuration Loading** (`app/core/config.py`)
```python
# Test cases needed:
# - load_settings() returns empty Settings when file missing
# - load_settings() parses valid YAML with Pydantic validation
# - Settings.model_validate() rejects invalid database types
# - find_database(settings, name) returns correct config or None
# - find_llm(settings, name) returns correct config or None
# - Sensitive passwords handled safely (not logged)
```

### Priority 2: External API Integration

**4. LLM Adapters** (`app/adapters/llm/openai_adapter.py`, `app/adapters/llm/ollama_adapter.py`)
```python
# Test cases needed:
# - generate_sql() formats messages with system prompt + schema + history
# - API key resolution (config value takes precedence over env var)
# - Custom endpoint/headers passed to OpenAI client
# - stream_text() yields non-empty chunks
# - Error handling for API timeouts/invalid keys
# - Temperature and max_tokens applied correctly
```

**5. Logging** (`app/core/logger.py`)
```python
# Test cases needed:
# - log_query() writes valid JSON to queries.log
# - log_llm() writes valid JSON to llm.log
# - Timestamp format is ISO 8601 UTC
# - Log directory created if missing
# - Multiple calls don't duplicate handlers (logger idempotent)
# - ensure_ascii=False preserves Korean text in logs
```

### Priority 3: Session & State

**6. Session State Helpers** (`app/core/session.py`)
```python
# Test cases needed:
# - get_chat_history() returns empty list if not initialized
# - append_chat() adds message to history with correct role
# - reset_chat() clears history
# - record_recent_query() enforces maxlen constraint
# - recent_queries() returns list in correct order (FIFO)
# - get_selected_db() returns None or persisted value
```

**7. Utility Functions** (`app/utils/schema.py`, `app/utils/export.py`)
```python
# Test cases needed:
# - summarize() truncates tables and columns beyond limits
# - summarize() handles empty schema gracefully
# - extract_sql_from_response() extracts code from ```sql blocks
# - extract_sql_from_response() handles markdown variations
# - to_csv_bytes() returns UTF-8-SIG encoded bytes
# - to_excel_bytes() writes valid .xlsx format
```

## Mocking Strategy

**Framework:** Would use `unittest.mock` (standard library) with `pytest` fixtures

**What to Mock:**
- Database connections: `SQLAlchemy.create_engine()` returns mock Engine
- External APIs: OpenAI chat.completions.create() returns mocked response object
- File I/O: `pathlib.Path.open()` returns mock file handles for config/auth files
- Streamlit functions: `st.session_state`, `st.cache_data()` not needed in unit tests (test domain logic separately from Streamlit UI)

**What NOT to Mock:**
- Pydantic models and validation logic (test actual parsing)
- SQL parsing via `sqlparse` (test actual parsing behavior)
- Local YAML/file operations (use temp files in fixtures)
- Core utility functions (test actual transformations)

**Mock Pattern Example:**
```python
from unittest.mock import Mock, patch, MagicMock
from app.adapters.db.mysql import MySQLAdapter
from app.core.config import DatabaseConfig

def test_mysql_connection_failure():
    config = DatabaseConfig(name="test", type="mysql", ...)
    adapter = MySQLAdapter(config)
    
    with patch('sqlalchemy.create_engine') as mock_engine:
        mock_engine.return_value.connect.side_effect = ConnectionError("timeout")
        ok, msg = adapter.test_connection()
        
        assert ok is False
        assert "timeout" in msg
```

## Fixtures and Test Data

**Test Data Location:** `tests/fixtures/`

**Factory Pattern for Configs:**
```python
# tests/conftest.py
import pytest
from app.core.config import DatabaseConfig, LLMConfig, Settings

@pytest.fixture
def sample_db_config():
    return DatabaseConfig(
        name="test_mysql",
        type="mysql",
        host="localhost",
        port=3306,
        database="testdb",
        user="testuser",
        password="testpass",
    )

@pytest.fixture
def sample_settings(sample_db_config):
    return Settings(
        databases=[sample_db_config],
        llms=[],
        app=AppConfig(default_database="test_mysql"),
    )
```

**Fixture Files:**
- `tests/fixtures/sample_schema.json`: Sample database schema for schema parsing tests
- `tests/fixtures/sample_responses/`: Directory with sample LLM responses for SQL extraction tests
- `tests/fixtures/test_settings.yaml`: Valid YAML for config loading tests

## Coverage

**Requirements:** None enforced currently

**Target:** 
- Critical modules (sql_safety, config, adapters): 80%+
- Utilities and helpers: 70%+
- Pages (Streamlit UI): Limited unit testing (integration tests more valuable)

**View Coverage (once tests added):**
```bash
pytest --cov=app tests/
pytest --cov=app --cov-report=html tests/
# Open htmlcov/index.html
```

## Test Types & Scope

**Unit Tests:**
- Test individual functions/methods in isolation with mocked dependencies
- Focus: Data transformation, validation, configuration parsing
- Files: `test_core/`, `test_utils/`, `test_adapters/` (mock DB/API calls)

**Integration Tests:**
- Test multiple components together (e.g., config loading + adapter building)
- Requires real test database or fixtures
- Would include: SQL safety + MySQL adapter query execution
- Currently infeasible without test database setup

**E2E Tests:**
- Not recommended for Streamlit (UI testing complex with `streamlit run`)
- Manual testing via Streamlit UI is current approach
- Could add Playwright/Selenium tests for critical workflows (expensive to maintain)

## Common Testing Patterns Needed

**Async Testing:**
- Not applicable (no async code in codebase)

**Error Testing:**
```python
def test_sql_safety_rejects_insert():
    result = validate_and_sanitize("INSERT INTO table VALUES (1, 2, 3)")
    assert result.ok is False
    assert "DDL" in result.reason or "금지" in result.reason

def test_config_validation_fails_on_invalid_type():
    with pytest.raises(ValidationError):
        DatabaseConfig(name="test", type="unsupported_db")
```

**Parametrized Tests:**
```python
import pytest

@pytest.mark.parametrize("forbidden_sql,reason", [
    ("DELETE FROM table", "DELETE"),
    ("DROP TABLE table", "DROP"),
    ("ALTER TABLE table ADD COLUMN id INT", "ALTER"),
])
def test_sql_safety_forbids_keyword(forbidden_sql, reason):
    result = validate_and_sanitize(forbidden_sql)
    assert result.ok is False
    assert reason in result.reason
```

---

## Recommendations to Add Tests

**Phase 1 (Highest Priority):**
1. Install pytest: `pip install pytest pytest-cov`
2. Create `tests/` directory structure
3. Add tests for `app/core/sql_safety.py` (35 lines, testable)
4. Add tests for `app/core/config.py` (86 lines, config validation critical)
5. Run: `pytest tests/test_core/ --cov=app.core`

**Phase 2:**
6. Mock-based tests for database adapters
7. Mock-based tests for LLM adapters
8. Fixture-based tests for session state helpers

**Phase 3:**
9. Integration tests with real database (requires test MySQL setup)
10. End-to-end tests for critical workflows

---

*Testing analysis: 2026-04-22*
