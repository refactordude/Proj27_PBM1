# Internal Data Platform — Agentic UFS Q&A (Streamlit)

An internal Streamlit app for querying a MySQL database of UFS (Universal
Flash Storage) device benchmark profiles. The Home page runs an **autonomous
ReAct agent loop** over OpenAI tool-calling: the user asks a UFS question in
plain language, and the agent iteratively dispatches `run_sql`,
`pivot_to_wide`, `normalize_result`, and `make_chart` against the read-only
`ufs_data` table until it can stream back a final answer with a chosen
Plotly chart. Explorer / Compare / Settings remain single-shot pages for
ad-hoc SQL and CRUD.

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

## Features

| Page | Description |
|---|---|
| 🏠 Home | **Agentic UFS Q&A** — streamed answer + collapsible tool trace + Plotly chart |
| 🔍 Explorer | Pick a table → filter / sort / paginate → CSV / Excel export |
| ↔️ Compare | Side-by-side comparison of two query results with diff highlighting |
| ⚙️ Settings | CRUD for DB / LLM configs · connection test |

### AI Q&A (Home page)

The Home page runs an autonomous **ReAct loop** over OpenAI tool-calling
(`chat.completions` with `tools=[...]`). Ask a UFS question in natural
language — the agent decides on each step whether to call `run_sql`
(SELECT against `ufs_data`), `pivot_to_wide` (long→wide reshape per UFS
spec §3), `normalize_result` (hex / compound / null cleaning per §5),
`get_schema` / `get_schema_docs` (context lookup), or `make_chart` (pick a
Plotly chart type and axis). Each step streams live with a collapsible trace
panel; the final answer includes the LLM-chosen chart. There is no "preview
SQL → click Execute" step — the agent runs the whole loop autonomously
inside the safety budget below.

- **Provider: OpenAI-only in v1.** The Home agent calls `chat.completions`
  with `tools=[...]`, which requires a tool-capable model (`gpt-4o`,
  `gpt-4o-mini`, `gpt-4.1-mini`). Other providers (Ollama, etc.) stay
  available on Settings / Compare / Explorer but cannot drive the Home loop.
- **Safety posture:** SELECT-only SQL (`sql_safety.validate_and_sanitize`),
  table allowlist `["ufs_data"]`, read-only session, and a per-turn budget
  (`max_steps=5`, `row_cap=200`, `timeout_s=30`) enforced inside the loop.
- **Observability:** every LLM round-trip and every SQL execution is
  appended as a JSONL line to `logs/llm.log` and `logs/queries.log`.

## Architecture

- **Adapter pattern** abstracts both DB and LLM: adding a new DB or model only requires writing an adapter class and registering it.
- **Agent loop** (`app/core/agent/`): stateless-per-turn ReAct dispatcher
  (`run_agent_turn`) + flat `TOOL_REGISTRY` of six tools; streamlit-agnostic
  so it can be unit-tested with a mocked OpenAI client.
- **SQL safety**: `sql_safety.py` allows SELECT-family statements only, auto-injects `LIMIT`, and blocks DDL/DML. Both `run_sql` and `pivot_to_wide` route through the same gate.
- **Read-only enforcement**: `readonly: true` option in Settings plus runtime verification — double protection.
- **Logging**: every query and LLM call is written to `logs/queries.log` and `logs/llm.log`.

## Directory layout

```
app/
  main.py              entry point (st.navigation)
  pages/               one page per F1–F6 (home = agentic Q&A)
  adapters/
    db/                DB adapters (mysql + registry)
    llm/               LLM adapters (openai, ollama + registry)
  core/                config / auth / logger / sql_safety / session
    agent/             ReAct loop + TOOL_REGISTRY (run_sql, pivot_to_wide,
                       normalize_result, get_schema, get_schema_docs, make_chart)
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
