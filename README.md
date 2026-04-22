# Internal Data Platform (Streamlit)

MVP based on PRD v0.1. Provides MySQL querying / comparison / export and
LLM-powered natural-language-to-SQL Q&A in a single Streamlit app.

## Quick start

```bash
# 1. Virtualenv
python -m venv .venv
source .venv/bin/activate

# 2. Dependencies
pip install -r requirements.txt

# 3. Configuration
cp config/settings.example.yaml config/settings.yaml
cp .env.example .env
# Open .env and set OPENAI_API_KEY

# 4. Run
streamlit run app/main.py
```

Default login: `admin` / `admin1234` (must be changed before deployment).

## Features (PRD F1–F6)

| Page | Description |
|---|---|
| 🏠 Home | Summary cards, natural-language → SQL (AI), recent query history |
| 🔍 Explorer | Pick a table → filter / sort / paginate → CSV / Excel export |
| ↔️ Compare | Side-by-side comparison of two query results with diff highlighting |
| ⚙️ Settings | CRUD for DB / LLM configs · connection test |

## Architecture

- **Adapter pattern** abstracts both DB and LLM: adding a new DB or model only requires writing an adapter class and registering it.
- **SQL safety**: `sql_safety.py` allows SELECT-family statements only, auto-injects `LIMIT`, and blocks DDL/DML.
- **Read-only enforcement**: `readonly: true` option in Settings plus runtime verification — double protection.
- **Logging**: every query and LLM call is written to `logs/queries.log` and `logs/llm.log`.

## Directory layout

```
app/
  main.py              entry point (st.navigation)
  pages/               one page per F1–F6
  adapters/
    db/                DB adapters (mysql + registry)
    llm/               LLM adapters (openai, ollama + registry)
  core/                config / auth / logger / sql_safety / session
  utils/               schema / export / viz
config/
  settings.yaml        DB/LLM registrations (edited via UI)
  auth.yaml            user accounts (bcrypt hashed)
logs/
```

## Adding a new DB (e.g. PostgreSQL)

1. Write `app/adapters/db/postgres.py` (subclass `DBAdapter`).
2. Register `"postgres": PostgresAdapter` in `app/adapters/db/registry.py`.
3. Pick the new type in the Settings UI and enter connection details.

## Adding a new LLM (e.g. Anthropic)

1. Write `app/adapters/llm/anthropic_adapter.py` (subclass `LLMAdapter`).
2. Register it in `app/adapters/llm/registry.py`.
3. Select it in the Settings UI.

## Docker

```bash
docker compose up --build
# http://localhost:8501
```

## Security checklist (PRD §5.2)

- [ ] Grant the LLM's MySQL account `GRANT SELECT` only
- [ ] Change the default admin password in `config/auth.yaml`
- [ ] Change `cookie.key`
- [ ] Keep `config/settings.yaml` in `.gitignore` (included by default)
- [ ] Expose only behind the corporate network / VPN

## Out of scope (PRD §1.3, v2+)

- Fine-grained RBAC
- Multiple concurrent DB connections
- SSO integration
- Public-internet exposure
