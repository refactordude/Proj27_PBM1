# Phase 1 — Session-State & Settings-UI Audit

**Phase:** 1 — Foundation
**Plan:** 05 Task 3
**Deliverable type:** Audit report (no code changes)
**Consumer:** Phase 4 planner — inherits the legacy-key removal list and the new-key convention
**Date:** 2026-04-23

## Purpose

Phase 1 Success Criterion 5 (from ROADMAP.md):
> A session-state audit confirms that orphan keys from the old Home flow
> (`pending_sql`, legacy chart keys) are namespaced or absent; no `KeyError`
> or stale-key collision occurs when both old and new code coexist during
> the Phase 4 swap.

This document is the audit artifact. Phase 1 makes **NO code changes** to
`app/pages/home.py`, `app/core/session.py`, `app/pages/settings_page.py`,
`app/pages/explorer.py`, or `app/pages/compare.py`. All findings here are
grep-sourced evidence only — the actual edits land in Phase 4 under the
HOME-02 / HOME-04 / HOME-05 requirement IDs.

## Session-State Key Inventory

| Key                | Defined in                                        | Purpose                                                  | Phase 1 Action                             | Phase 4 Action                       |
| ------------------ | ------------------------------------------------- | -------------------------------------------------------- | ------------------------------------------ | ------------------------------------ |
| `chat_history`     | `app/core/session.py:9` (`_CHAT_HISTORY_KEY`)     | Chat turns (role/content dict list)                      | Keep                                       | None (reused by HOME-04)             |
| `recent_queries`   | `app/core/session.py:10` (`_RECENT_QUERIES_KEY`)  | Sidebar recent-queries deque                             | Keep                                       | None (HOME-03)                       |
| `selected_db`      | `app/core/session.py:11` (`_SELECTED_DB_KEY`)     | Sidebar DB selection                                     | Keep                                       | None                                 |
| `selected_llm`     | `app/core/session.py:12` (`_SELECTED_LLM_KEY`)    | Sidebar LLM selection                                    | Keep                                       | None                                 |
| `user`             | `app/core/auth.py` (via `streamlit_authenticator`) | Authenticated username for audit logging                 | Keep                                       | None                                 |
| `pending_sql`      | `app/pages/home.py` (7 occurrences)               | **Legacy**: LLM-generated SQL awaiting user confirmation | **Audit only — do NOT touch this phase**   | **Remove (HOME-02)**                 |
| `pending_sql_edit` | `app/pages/home.py` (1 occurrence, widget key)    | **Legacy**: `st.text_area` widget key for SQL editing    | **Audit only — do NOT touch this phase**   | **Remove (HOME-02)**                 |
| `cmp_a`, `cmp_b`   | `app/pages/compare.py:68-72`                      | Compare page side-by-side DataFrame buffers              | Keep                                       | None (HOME-05 preserved)             |
| `explorer_df`      | `app/pages/explorer.py:72-106`                    | Explorer page DataFrame buffer                           | Keep                                       | None (HOME-05 preserved)             |

## Legacy Home Keys — Phase 4 Removal List

These keys MUST be removed by Phase 4 along with the old one-shot SQL flow
(HOME-02 requirement):

1. `pending_sql` — the old NL→SQL preview state
2. `pending_sql_edit` — the `st.text_area` widget key for SQL editing

**Evidence collected from `grep -n "pending_sql" app/pages/home.py`:**

```
102:            st.session_state["pending_sql"] = sql_only
104:    pending_sql: str | None = st.session_state.get("pending_sql")
105:    if pending_sql:
110:            value=pending_sql,
111:            key="pending_sql_edit",
140:                    st.session_state["pending_sql"] = None
150:            st.session_state["pending_sql"] = None
```

Total: 7 occurrences of `pending_sql` (including one `pending_sql_edit`
widget key on line 111). All seven lines live inside a single
confirm-then-execute block that Phase 4 will delete wholesale when it
replaces the NL→SQL preview UI with the agent-loop turn UI.

**Auxiliary evidence — all other `st.session_state` uses in home.py
(`grep -n "st.session_state" app/pages/home.py`):**

```
83:                        user=st.session_state.get("user", "unknown"),
91:                        user=st.session_state.get("user", "unknown"),
102:            st.session_state["pending_sql"] = sql_only
104:    pending_sql: str | None = st.session_state.get("pending_sql")
129:                        user=st.session_state.get("user", "unknown"),
140:                    st.session_state["pending_sql"] = None
143:                        user=st.session_state.get("user", "unknown"),
150:            st.session_state["pending_sql"] = None
```

The only non-`pending_sql` home.py session-state touches are read-only
`st.session_state.get("user", "unknown")` calls for audit logging (lines
83, 91, 129, 143) — these are SAFE and Phase 4 MUST preserve them.

**Chart-related legacy check (`grep -n "auto_chart" app/pages/home.py`):**

```
19:from app.utils.viz import auto_chart
137:                    chart = auto_chart(df)
```

`auto_chart` is a pure utility call, NOT a session-state key. The
`auto_chart` import will go away in Phase 4 when the LLM chooses the
chart (UX-04) instead of the rule-based `app.utils.viz.auto_chart`
picker, but it does NOT introduce any session-state orphans.

## Recommended New Agent-Era Key Convention

For Phase 4 (which introduces the per-turn trace expander, UX-03, and
any future cross-turn memory, MEM-01):

```python
# app/core/session.py — Phase 4 adds these; Phase 1 only documents
_AGENT_TRACE_KEY = "agent_trace_v1"
```

### Rationale

- **`_v1` suffix future-proofs against v2 shape changes.** MEM-01's cross-turn
  memory may change the trace schema later; versioning the key now lets Phase 4
  and Phase 5 coexist on different session-state shapes without a migration script.
- **Single prefix avoids scattered agent-related keys.** Rather than
  `agent_trace`, `agent_steps`, `agent_tool_calls` scattered across modules,
  everything agent-related lives under one key whose value is a structured
  dict. One key, one test, one cleanup path.
- **No DataFrame cache session key needed.** Per AGENT-07
  (stateless-per-turn), the DataFrame cache lives on
  `AgentContext._df_cache` (instance attribute, built fresh each turn —
  see `app/core/agent/context.py`). It is NEVER promoted to `st.session_state`.
  So Phase 4 MUST NOT add a `_df_cache_*` session key.

### Constraint on Phase 4

Phase 4 MUST NOT reuse any legacy key name for new meaning. Specifically:
- Do NOT repurpose `pending_sql` as an agent trace slot.
- Do NOT repurpose `pending_sql_edit` as any new widget key.
- The pre-existing `chat_history` key IS reused by HOME-04 (the per-turn chat
  rendering is agent-aware from Phase 4 onward) — that is intentional and
  explicitly scoped by HOME-04.

## Settings UI Audit (OBS-03 Compliance)

OBS-03 requires that `AgentConfig` be editable via YAML but **NOT** via the
Settings UI in v1. Phase 5 Task 1 composed `AppConfig.agent: AgentConfig`.
This section confirms that the composition does NOT leak into the UI.

**Method:** Read `app/pages/settings_page.py` end-to-end + grep for
field-iteration patterns that would recursively descend into Pydantic
submodels (`model_fields`, `__fields__`, `AppConfig.__fields__.items()`,
etc.).

### Finding: Option A (expected) — UI uses explicit per-field widgets

`app/pages/settings_page.py` renders each `AppConfig` field via explicit,
hand-written `st.selectbox` / `st.number_input` calls keyed on specific
attribute names (`default_database`, `default_llm`, `query_row_limit`,
`recent_query_history`). There is NO loop over `AppConfig.model_fields` or
`AppConfig.__fields__`. The new `AppConfig.agent: AgentConfig` field is
therefore NOT surfaced in the UI.

**OBS-03 is satisfied without any code change. No Phase 4 follow-up required.**

**Evidence from `grep -nE "AppConfig|AgentConfig|model_fields|__fields__" app/pages/settings_page.py`:**

```
(empty — no matches)
```

The empty grep output is dispositive: `settings_page.py` never references
the Pydantic class objects or their field-introspection APIs. It only
imports `DatabaseConfig` and `LLMConfig` as constructors for the list-CRUD
forms, and accesses `s.app.<field>` attributes by explicit name.

**Auxiliary evidence — the app-defaults tab renders exactly four explicit
fields and nothing else** (from `app/pages/settings_page.py:130-158`):

```python
# ----- App defaults ---------------------------------------------------------
with tab_app:
    st.subheader("기본값 / 동작")
    ...
    default_db = st.selectbox("기본 DB", db_names, ...)                   # s.app.default_database
    default_llm = st.selectbox("기본 LLM", llm_names, ...)                # s.app.default_llm
    row_limit = st.number_input("기본 row limit", 10, 1_000_000, ...)     # s.app.query_row_limit
    hist = st.number_input("최근 질의 보관 개수", 1, 200, ...)            # s.app.recent_query_history
    if st.button("저장", type="primary"):
        s.app.default_database = ...
        s.app.default_llm = ...
        s.app.query_row_limit = ...
        s.app.recent_query_history = ...
        save_settings(s)
```

Four explicit field reads + four explicit field writes. `s.app.agent` is
never touched, read, or rendered. Operators must edit
`config/settings.yaml` directly to tune agent budgets — exactly what
OBS-03 requires for v1.

## Phase 1 Scope Boundary

- **This phase modifies ONLY:**
  - `app/core/agent/*` (new package: `config.py`, `context.py`, `tools/_base.py`)
  - `app/core/config.py` (one import + one new `AppConfig.agent` field, Plan 05 Task 1)
  - `app/adapters/llm/openai_adapter.py` (`httpx.Timeout(30.0)` fix, Plan 04)
  - `config/settings.example.yaml` (documentation of new `app.agent` block, Plan 05 Task 1)
  - `tests/**` (new unit-test modules across Plans 01–05)
  - `.planning/phases/01-foundation/*.md` (planning artifacts, including this file)

- **This phase DOES NOT modify:**
  - `app/pages/home.py`
  - `app/core/session.py`
  - `app/pages/settings_page.py`
  - `app/pages/explorer.py`
  - `app/pages/compare.py`

- **Verified by:**

  ```bash
  git diff --name-only app/pages/home.py app/core/session.py \
    app/pages/settings_page.py app/pages/explorer.py app/pages/compare.py
  # Expected output: empty
  ```

  (Run this against the Phase 1 branch HEAD; an empty result confirms
  the scope boundary was honored.)

## Phase 4 Handoff Checklist

When Phase 4 begins, its planner MUST consult this document and:

1. Remove `pending_sql` (lines 102, 104, 105, 110, 140, 150) and
   `pending_sql_edit` (line 111) from `app/pages/home.py` along with the
   enclosing confirm-then-execute block (HOME-02).
2. Introduce `_AGENT_TRACE_KEY = "agent_trace_v1"` in `app/core/session.py`
   alongside the existing four `_KEY` constants, and add matching
   `get_agent_trace()` / `set_agent_trace()` helpers.
3. Preserve all four existing session-state keys in `app/core/session.py`
   verbatim (`chat_history`, `recent_queries`, `selected_db`, `selected_llm`).
4. Preserve all session-state usage in `app/pages/compare.py` (`cmp_a`,
   `cmp_b`) and `app/pages/explorer.py` (`explorer_df`) under HOME-05.
5. Re-run `grep -nE "AppConfig|AgentConfig|model_fields|__fields__" app/pages/settings_page.py`
   after any edit to that page; if it becomes non-empty, add an
   `if field_name == "agent": continue` guard to preserve OBS-03.
