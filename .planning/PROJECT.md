# Internal Data Platform — Agentic UFS Q&A

## What This Is

A Streamlit-based internal data platform for querying a MySQL database of UFS (Universal Flash Storage) device benchmark profiles. The current milestone replaces the existing "generate-SQL-and-confirm" NL interface on Home with an **agentic LLM engine** that autonomously runs SELECT queries against the UFS dataset, inspects results, iterates, and returns a streamed answer plus an LLM-chosen Plotly chart.

## Core Value

Ask a UFS question in plain language and get a correct, visualized answer — without manually writing or confirming SQL — on a safety-bounded read-only loop over the UFS benchmarking database.

## Requirements

### Validated

<!-- Inherited from shipped MVP (PRD v0.1) and confirmed by the existing codebase. -->

- ✓ Streamlit multi-page app with sidebar DB/LLM selector — existing
- ✓ MySQL adapter with connection pooling and connection test — existing (`app/adapters/db/mysql.py`)
- ✓ OpenAI LLM adapter (`generate_sql`, `stream_text`) — existing (`app/adapters/llm/openai_adapter.py`)
- ✓ Ollama LLM adapter (non-agentic) — existing (`app/adapters/llm/ollama_adapter.py`)
- ✓ Adapter registries for runtime plugin selection — existing (`app/adapters/db/registry.py`, `app/adapters/llm/registry.py`)
- ✓ SELECT-only SQL safety (`sql_safety.validate_and_sanitize`, auto-LIMIT injection) — existing
- ✓ Read-only DB enforcement (per-connection `SET SESSION TRANSACTION READ ONLY`) — existing
- ✓ Streamlit-authenticator login with bcrypt credentials in YAML — existing
- ✓ JSONL query + LLM logging (`pbm.query`, `pbm.llm`) — existing (`app/core/logger.py`)
- ✓ Explorer page: table browser with filter / sort / paginate / CSV+Excel export — existing (F2)
- ✓ Compare page: side-by-side diff of two query results — existing (F3)
- ✓ Settings page: CRUD for DB and LLM configs, connection test — existing (F6)
- ✓ Heuristic `auto_chart()` Plotly visualization on result sets — existing (`app/utils/viz.py`)
- ✓ Pydantic-based typed config models (`Settings`, `DatabaseConfig`, `LLMConfig`, `AppConfig`) — existing
- ✓ Docker / docker-compose deployment — existing

### Active

<!-- Current milestone. Hypotheses until shipped. -->

- [ ] Replace Home AI Q&A with a ReAct-style agentic loop over OpenAI tool-calling (raw `chat.completions` with `tools=[...]`)
- [ ] `run_sql` tool: executes through existing `sql_safety.validate_and_sanitize`, auto-LIMIT=200, table allowlist `["ufs_data"]`
- [ ] `get_schema` tool: returns tables, columns, distinct `PLATFORM_ID` and `InfoCatergory` values for disambiguation
- [ ] `pivot_to_wide(category, item)` tool: server-side long→wide pivot per UFS spec §3
- [ ] `normalize_result(values)` tool: applies UFS spec §5 `clean_result` helper (hex, "None"/errors → NULL, compound `local=…,peer=…` splitter)
- [ ] `get_schema_docs(section)` tool: retrieves sections §1–§7 of the UFS schema spec on demand (not baked into system prompt)
- [ ] `make_chart` tool: `chart_type ∈ {bar, line, scatter, heatmap}`, `x`, `y`, `color`, `title`, `data_ref` — returns Plotly figure rendered via `st.plotly_chart`
- [ ] Per-turn budget enforcement: `max_steps=5`, `row_cap=200`, `timeout_s=30`
- [ ] Streamed + collapsible trace UX: each step (model thinking, SQL, tool result row count, chart) streams live; full trace collapses into an expander after the final answer
- [ ] Stateless per user turn (no cross-turn DataFrame reference / `result_N` IDs in v1)
- [ ] Remove the existing "generate SQL → confirm → execute" flow from `app/pages/home.py`; Explorer / Compare / Settings must continue to work unchanged
- [ ] Focused test coverage: unit tests for each new tool + one integration test for the loop with a mocked OpenAI client
- [ ] Ship bar: seeded `ufs_data` DB answers 3 representative UFS questions correctly with streamed trace + Plotly chart:
  1. Cross-device compare — "Compare `wb_enable` across all devices."
  2. Top-N / ranking — "Which devices have the largest `total_raw_device_capacity`?"
  3. Brand-vs-brand — "Compare `life_time_estimation_a` for Samsung vs OPPO devices."

### Out of Scope

<!-- v1 boundaries, with reasoning so they don't get re-added. -->

- Ollama, Anthropic, or any non-OpenAI provider in the agentic loop — OpenAI tool-calling only in v1; Ollama/Anthropic adapters stay for the non-agentic code paths (Settings CRUD, Compare) but cannot drive the loop. Why: testing surface and tool-calling API divergence; revisit once v1 UX is validated.
- General-purpose agentic Q&A over arbitrary MySQL schemas — UFS-specialized in v1. Why: schema-aware prompting (Result quirks, long/wide pivot idiom) is the value-add; a general mode dilutes it.
- Cross-turn memory / result references ("now show that as a chart", "filter the previous result") — stateless per turn. Why: keeps the loop simple and cheap; reconsider after v1 usage reveals whether follow-ups are common.
- Frameworks (LangGraph, OpenAI Agents SDK, LangChain) — raw OpenAI `chat.completions` + `tools=[...]` loop only. Why: ~200 lines, no dependency cost, full control over streaming + budget enforcement.
- Comprehensive test backfill for existing SQL-safety / adapters / auth modules — deferred. Why: the hard-cap + allowlist guardrails already bound blast radius; backfill is a separate hardening milestone. The 3 high-risk concerns in `.planning/codebase/CONCERNS.md` (SQL injection via WHERE clause, credential storage, log rotation) stay on the backlog.
- RBAC, SSO, multi-concurrent DB sessions — per PRD §1.3 / README "Out of scope".
- Saved reports, scheduled queries, dashboards — not requested for this milestone.
- Chart libraries beyond Plotly — aligned with existing `app/utils/viz.py`; Altair stays unused even though it's in `requirements.txt`.
- New chart types beyond `bar / line / scatter / heatmap` — minimum viable surface; extendable later without schema change.

## Context

**Domain.** The UFS benchmarking database (`ufs_data`) stores per-device UFS subsystem profiles in **long/narrow** format — one row per parameter per device. Each row has `(PLATFORM_ID, InfoCatergory, Item, Result)`. Cross-device analysis requires pivoting into a wide `device × parameter` matrix, which MySQL cannot do dynamically — this is why `pivot_to_wide` has to be a server-side helper tool for the agent. The `Result` field is **untrusted text** (hex, decimal, CSV list, `"None"`, error strings, compound `local=…,peer=…`); naive numeric aggregation fails on it, which is why `normalize_result` must exist as a tool and not rely on the LLM to parse it.

**Existing architecture.** Layered adapter pattern (`app/adapters/db/`, `app/adapters/llm/`) with registries for runtime plugin selection; `app/core/runtime.py` resolves the selected DB and LLM per page. The current Home NL→SQL (`app/pages/home.py`) is a **single-shot, user-in-the-loop** flow: LLM generates SQL once, user reviews/edits in a text area, clicks Execute, adapter runs it, `auto_chart()` tries a heuristic Plotly render. The LLM never sees query results. This milestone fundamentally changes that control flow on Home only — Explorer, Compare, and Settings stay single-shot.

**Safety posture.** Three pre-existing layers must survive unchanged:
1. `sql_safety.validate_and_sanitize` (SELECT-only regex + `sqlparse`, auto-LIMIT).
2. `MySQLAdapter.run_query` (`SET SESSION TRANSACTION READ ONLY` when config has `readonly: true`).
3. Deployment-level DB credential with `GRANT SELECT` only.

The agentic loop adds two more: a **table allowlist** (`["ufs_data"]` — the agent cannot query other tables even if they exist in the connected DB) and a **per-turn query budget** (`max_steps=5` hard cap).

**Known risks / codebase concerns relevant to this milestone.** From `.planning/codebase/CONCERNS.md`:
- No existing tests — SQL safety regressions currently ship undetected. New tools must ship with tests; SQL-safety coverage is still deferred.
- OpenAI calls have no timeout — must add `timeout=30` per `openai_adapter.py` for the agent loop.
- Empty LLM response handling — agent must treat empty tool-call responses as a terminal step, not a silent failure.
- SQL extraction regex is fragile — bypassed in the agent path since the LLM emits tool-call arguments directly (no prose→SQL extraction).

**Observability.** All tool calls must log to `logs/llm.log` and `logs/queries.log` via existing `log_llm` / `log_query` helpers — the trace UI is mirrored by the existing JSONL logs for audit.

## Constraints

- **Tech stack**: Python 3.11 + Streamlit 1.40+ + SQLAlchemy 2.0 + pymysql + Plotly + Pydantic 2 + OpenAI SDK 1.50+ — the agentic engine must fit this stack without adding new frameworks.
- **Provider**: OpenAI-only for the agentic loop in v1 (`chat.completions` with `tools=[...]`, tool-capable model required — gpt-4o / gpt-4o-mini).
- **Database**: MySQL read-only; single table `ufs_data` is the only allowed target of `run_sql` in v1.
- **Safety**: SELECT-only + auto-LIMIT + table allowlist + `max_steps=5` per turn are non-negotiable; any change to these requires explicit approval.
- **Deployment**: Must continue to run via `streamlit run app/main.py` and `docker compose up` without new services.
- **Auth**: Behind existing `streamlit-authenticator` login — no new auth surface.
- **Compatibility**: Explorer / Compare / Settings pages must function unchanged after Home is rewritten.
- **Budget**: Hard per-turn ceiling — `max_steps=5`, `row_cap=200`, `timeout_s=30` — configurable in `AppConfig` but defaults are conservative.
- **Dependencies added** (expected): none required beyond what's already in `requirements.txt`; OpenAI SDK 1.50+ already supports tools.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Multi-step ReAct loop (vs. two-step or approval-gated) | User wants autonomous drill-down; existing guardrails (SELECT-only, allowlist, `max_steps=5`) bound blast radius. | — Pending |
| Replace Home AI Q&A entirely (vs. new page / mode toggle) | Single clear UX; avoids maintaining two NL flows; the user-confirm step is no longer meaningful when the agent iterates. | — Pending |
| UFS-specialized (vs. general) | The whole value is schema-aware reasoning (Result quirks, pivot idiom). Generic agent would require the user to re-teach the schema every turn. | — Pending |
| Schema docs retrieved on demand via `get_schema_docs` tool (vs. baked into system prompt) | Keeps every-turn token cost low; agent pulls only the section relevant to the current question. | — Pending |
| Stateless per turn in v1 (vs. conversation + result refs) | Simpler; cheaper; postpones `result_N` id scheme and DataFrame cache until we see whether follow-ups are a common pattern. | — Pending |
| LLM picks chart via `make_chart` tool (vs. heuristic `auto_chart`) | Cross-device UFS comparisons need chart-type reasoning (heatmap vs bar vs line) the heuristic can't do. | — Pending |
| Raw OpenAI `chat.completions` + `tools=[]` loop (vs. Agents SDK / LangGraph) | OpenAI-only + simple replace + ship-fast intent — framework is dead weight. | — Pending |
| `row_cap=200` + "refine" semantics (vs. auto-sample + summarize) | Forces agent to write aggregating SQL; raw rows stay below a context-window threshold. If exceeded, tool returns a refine signal instead of truncated rows. | — Pending |
| Focused new-code tests only (vs. comprehensive backfill) | Existing SQL-safety gaps are known; this milestone is additive, not a hardening cycle. | — Pending |
| OpenAI-only for the agent in v1 (vs. Ollama / Anthropic parity) | Tool-calling API divergence; smallest testing surface; revisit after v1 validates UX. | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-22 after initialization*
