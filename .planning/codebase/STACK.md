# Technology Stack

**Analysis Date:** 2026-04-22

## Languages

**Primary:**
- Python 3.11 - Web application, data processing, LLM adapters

## Runtime

**Environment:**
- Python 3.11-slim (Docker base image)

**Package Manager:**
- pip (dependency management)
- Lockfile: `requirements.txt` (pinned versions present)

## Frameworks

**Core:**
- Streamlit 1.40+ - Web UI framework for data platform
- streamlit-authenticator 0.3.3+ - User authentication and session management

**Database Access:**
- SQLAlchemy 2.0+ - ORM and database abstraction layer
- pymysql 1.1+ - MySQL driver for SQLAlchemy

**Data Processing:**
- pandas 2.2+ - DataFrame operations for query results
- openpyxl 3.1+ - Excel file export support

**LLM Integration:**
- openai 1.50+ - OpenAI API client (GPT-4o, GPT-4o-mini)
- requests 2.32+ - HTTP client for Ollama and other HTTP-based APIs

**Visualization:**
- Plotly 5.22+ - Interactive charting and visualization
- Altair 5.3+ - Declarative charting library

**Configuration & Validation:**
- Pydantic 2.7+ - Data validation and settings management
- PyYAML 6.0+ - YAML configuration file parsing
- python-dotenv 1.0+ - Environment variable loading from .env

**Security:**
- bcrypt 4.2+ - Password hashing for authentication

**Utilities:**
- sqlparse 0.5+ - SQL parsing and validation

## Key Dependencies

**Critical:**
- openai 1.50+ - Required for main AI query generation via OpenAI API
- streamlit 1.40+ - Core UI framework
- SQLAlchemy 2.0+ - Database abstraction for multi-database support

**Infrastructure:**
- pymysql 1.1+ - MySQL connectivity
- requests 2.32+ - HTTP requests for Ollama and external APIs
- pandas 2.2+ - Data manipulation and export

## Configuration

**Environment:**
- Loaded via `python-dotenv` from `.env` file (see `.env.example`)
- Path override: `SETTINGS_PATH` environment variable
- Auth override: `AUTH_PATH` environment variable
- Log override: `LOG_DIR` environment variable

**Key Configs Required:**
- `OPENAI_API_KEY` - OpenAI API key (can be set in environment or settings UI)
- `config/settings.yaml` - Database and LLM configuration (auto-managed via Settings UI)
- `config/auth.yaml` - User credentials and authentication settings

**Build:**
- `Dockerfile` - Multi-stage build with Python 3.11-slim base
- `docker-compose.yml` - Service orchestration (app service configured, MySQL service optional/commented)

## Platform Requirements

**Development:**
- Python 3.11+
- pip package manager
- Git (for version control)

**Production:**
- Docker (containerized deployment)
- Python 3.11 runtime
- MySQL 8.0+ (or supported alternative database)
- Network access to OpenAI API (if using OpenAI models)
- Optionally: Ollama for local LLM support

---

*Stack analysis: 2026-04-22*
