# External Integrations

**Analysis Date:** 2026-04-22

## APIs & External Services

**LLM Providers:**
- OpenAI - SQL generation and text streaming via GPT-4o/GPT-4o-mini
  - SDK/Client: `openai>=1.50`
  - Auth: `OPENAI_API_KEY` environment variable or configured in `config/settings.yaml`
  - Implementation: `app/adapters/llm/openai_adapter.py`
  - Supports custom endpoint via `endpoint` config field

- Ollama - Local LLM support for on-premises deployments
  - SDK/Client: `requests>=2.32` (HTTP-based API)
  - Auth: None required (local service)
  - Implementation: `app/adapters/llm/ollama_adapter.py`
  - Default endpoint: `http://localhost:11434`
  - Configurable via `endpoint` and `model` in settings

**LLM Configuration (in settings.yaml):**
- Type field supports: `openai`, `anthropic`, `ollama`, `vllm`, `custom`
- Currently implemented: `openai`, `ollama`
- Planned but commented: `anthropic`, `vllm`

## Data Storage

**Databases:**
- MySQL 8.0+ (primary support)
  - Connection: Configured in `config/settings.yaml` under `databases` section
  - Client: SQLAlchemy 2.0+ with pymysql driver
  - Multiple database support via adapter pattern
  - Read-only enforcement via `readonly` flag in config
  - Implementation: `app/adapters/db/mysql.py`

**File Storage:**
- Local filesystem only
  - Configuration files: `config/` directory
  - Logs: `logs/` directory (default, configurable via `LOG_DIR`)
  - Exports: Memory-based (pandas DataFrame to CSV/Excel)
  - Export helper: `app/utils/export.py`

**Caching:**
- Streamlit session_state - In-memory session caching only
- No external cache service configured

## Authentication & Identity

**Auth Provider:**
- Custom file-based authentication
  - Implementation: `app/core/auth.py` with `streamlit-authenticator>=0.3.3`
  - Credentials stored in: `config/auth.yaml`
  - Default account: `admin` / `admin1234` (bcrypt hashed)
  - Cookie-based session management
  - Cookie name: `pbm_auth` (configurable in auth.yaml)
  - Expiry: 7 days (configurable in auth.yaml)

## Monitoring & Observability

**Error Tracking:**
- None configured
- Exceptions logged to application logs

**Logs:**
- File-based JSONL logging
  - Query logs: `logs/queries.log`
    - Records: user, database, SQL, row count, duration, errors
    - Implementation: `app/core/logger.py` (log_query function)
  - LLM logs: `logs/llm.log`
    - Records: user, model, question, generated SQL, duration, errors
    - Implementation: `app/core/logger.py` (log_llm function)
  - Recent history: Stored in Streamlit `session_state`

## CI/CD & Deployment

**Hosting:**
- Docker containers (self-hosted)
  - Image: Python 3.11-slim with pip dependencies
  - Port: 8501 (Streamlit default)
  - Health check: HTTP curl to `/_stcore/health`

**CI Pipeline:**
- None detected
- Manual deployment via Docker/docker-compose

**docker-compose Configuration:**
- App service: Builds from `Dockerfile`, runs on port 8501
- MySQL service: Optional (commented out) - assumes use of existing internal MySQL infrastructure
- Environment pass-through: `OPENAI_API_KEY`
- Volume mounts: `./config:/app/config`, `./logs:/app/logs`

## Environment Configuration

**Required env vars:**
- `OPENAI_API_KEY` - OpenAI API key (if using OpenAI LLM)

**Optional env vars:**
- `SETTINGS_PATH` - Override default settings.yaml location (default: `config/settings.yaml`)
- `AUTH_PATH` - Override default auth.yaml location (default: `config/auth.yaml`)
- `LOG_DIR` - Override default logs directory (default: `logs/`)

**Secrets location:**
- `.env` file (git-ignored, not committed)
- See `.env.example` for template
- Environment variables passed via docker-compose

## Webhooks & Callbacks

**Incoming:**
- None configured

**Outgoing:**
- None configured

## Database Adapters

**Implemented:**
- MySQL - `app/adapters/db/mysql.py`
  - Registry: `app/adapters/db/registry.py`
  - Adapter pattern allows easy addition of new database types

**Configured but Not Implemented:**
- postgres - Commented example in registry
- MSSQL, BigQuery, Snowflake - Supported in Pydantic config but no adapters

## LLM Adapters

**Implemented:**
- OpenAI - `app/adapters/llm/openai_adapter.py`
  - Supports chat.completions API with custom headers
  - Models: Configurable (default: gpt-4o-mini)

- Ollama - `app/adapters/llm/ollama_adapter.py`
  - Uses `/api/chat` endpoint
  - Streaming support for both implementations
  - Registry: `app/adapters/llm/registry.py`

**Configured but Not Implemented:**
- Anthropic - Commented in registry
- vLLM - OpenAI-compatible, can use OpenAIAdapter with custom endpoint

---

*Integration audit: 2026-04-22*
