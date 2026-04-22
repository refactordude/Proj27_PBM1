# Roadmap: Internal Data Platform — Agentic UFS Q&A

## Overview

Five coarse phases deliver a complete ReAct-style agentic loop that replaces the existing one-shot NL→SQL flow on Home. Build order is bottom-up and forced by the dependency graph: agent configuration and typing contracts must exist before any tool can import them; all six tools (and their safety guardrails) must be independently testable before the loop controller can dispatch them; the loop must be fully unit-tested before the Streamlit UI rendering layer wires into it; and the Home page rewrite (which irreversibly deletes the old flow) is last. Phase 5 drives the ship-bar E2E validation and closes any remaining test gaps.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Foundation** - Agent config, context, and tool protocol contracts; session-state hygiene; OpenAI timeout fix
- [ ] **Phase 2: Tool Implementations** - All 6 tools + unit tests + safety guardrails + spec files + typo grep test
- [ ] **Phase 3: Agent Loop Controller** - run_agent_turn, parallel_tool_calls=False, forced finalization, budget accounting, loop integration tests
- [ ] **Phase 4: Streaming + Trace UX** - Home page rewrite with st.status / st.write_stream / trace expander; old flow deletion; Ollama guard
- [ ] **Phase 5: Test & Polish** - Complete test coverage, manual E2E ship-bar scenarios, log sanity check, doc updates

## Phase Details

### Phase 1: Foundation
**Goal**: The shared contracts that every downstream component imports exist and are correct — `AgentConfig`, `AgentContext`, the `Tool` protocol, `ToolResult`, and the OpenAI timeout fix — so Phase 2 tools can be written and tested in isolation without blocked imports.
**Depends on**: Nothing (first phase)
**Requirements**: AGENT-07, AGENT-08, AGENT-09, OBS-03
**Success Criteria** (what must be TRUE):
  1. `from app.core.agent.config import AgentConfig` succeeds and an instance with defaults (`max_steps=5`, `row_cap=200`, `timeout_s=30`, `allowed_tables=["ufs_data"]`, `max_context_tokens=30000`, `model="gpt-4.1-mini"`) can be constructed and serialized by Pydantic without error.
  2. `from app.core.agent.context import AgentContext` succeeds and a fresh context object holds a `_df_cache` dict that is distinct across two separate instantiations (no shared mutable state).
  3. `from app.core.agent.tools._base import Tool, ToolResult` succeeds; a toy function decorated or typed as `Tool` passes a `isinstance` / Protocol check.
  4. `openai_adapter.py` passes `timeout=httpx.Timeout(30.0)` on every `chat.completions.create` call — verifiable by grepping the file or by a unit test that inspects the call kwargs.
  5. A session-state audit confirms that orphan keys from the old Home flow (`pending_sql`, legacy chart keys) are namespaced or absent; no `KeyError` or stale-key collision occurs when both old and new code coexist during the Phase 4 swap.
**Plans**: 5 plans
- [x] 01-01-PLAN.md — AgentConfig Pydantic model + defaults/bounds/round-trip tests
- [x] 01-02-PLAN.md — AgentContext dataclass with instance-level _df_cache + tests
- [x] 01-03-PLAN.md — Tool Protocol (@runtime_checkable) + ToolResult Pydantic model + tests
- [x] 01-04-PLAN.md — OpenAI adapter httpx.Timeout(30.0) wiring on both call sites + tests
- [x] 01-05-PLAN.md — AppConfig.agent composition + YAML round-trip test + settings_page + session-state audit

### Phase 2: Tool Implementations
**Goal**: All six agent tools are implemented, safety-hardened, registered in the flat `TOOL_REGISTRY`, and independently tested — meaning Phase 3 can import and dispatch any tool without touching tool code again.
**Depends on**: Phase 1
**Requirements**: TOOL-01, TOOL-02, TOOL-03, TOOL-04, TOOL-05, TOOL-06, TOOL-07, TOOL-08, SAFE-01, SAFE-02, SAFE-03, SAFE-04, SAFE-05, SAFE-07, OBS-01, TEST-01, TEST-04
**Note on parallelization**: The six tool files (`run_sql`, `get_schema`, `pivot_to_wide`, `normalize_result`, `get_schema_docs`, `make_chart`) are independently implementable once Phase 1's Tool protocol exists. With `parallelization=true` in config, the planner should spawn concurrent plans for subsets of these tools rather than serializing them.
**Success Criteria** (what must be TRUE):
  1. Running `pytest app/core/agent/tools/` passes all unit tests — each of the 6 tools has tests covering happy path, one Pydantic argument-validation failure, and one domain edge case (allowlist rejection for `run_sql`, compound-value split for `normalize_result`, `aggfunc="first"` de-dup for `pivot_to_wide`).
  2. `run_sql` rejects a query referencing `information_schema` or any table outside `["ufs_data"]` with a clear error before any DB adapter is called — verifiable by unit test with a mocked DB adapter that must not be called.
  3. Every `run_sql` tool result is wrapped in the untrusted-data framing envelope and each cell is hard-capped at 500 characters — verifiable by unit test inspecting the returned `ToolResult.content` string.
  4. `pytest app/core/agent/tools/test_no_correct_spelling.py` (the `InfoCategory` grep test) fails when a correctly-spelled occurrence is injected into a temp file under `app/core/agent/`, confirming the CI guard works.
  5. `from app.core.agent.tools import TOOL_REGISTRY` returns a dict with exactly 6 entries, each value passing the `Tool` Protocol check.
**Plans**: TBD
**UI hint**: no

### Phase 3: Agent Loop Controller
**Goal**: `run_agent_turn(user_message) -> Iterator[AgentStep]` is fully implemented, enforces all budget constraints, and is verified by integration tests with a mocked OpenAI client — so the loop is proven correct before any Streamlit code touches it.
**Depends on**: Phase 2
**Requirements**: AGENT-01, AGENT-02, AGENT-03, AGENT-04, AGENT-05, AGENT-06, OBS-02, TEST-02, TEST-03, TEST-05
**Success Criteria** (what must be TRUE):
  1. The integration test `test_react_loop_run_sql_then_answer` (mocked OpenAI `side_effect=[tool_response, text_response]`) passes, asserting the returned `AgentStep` sequence contains one tool step and one final-answer step, and that `chat.completions.create` was called exactly twice.
  2. The integration test `test_forced_finalization_on_budget_exhaustion` passes — a mocked loop where all 5 responses are tool calls (never a stop) must emit a final text-only `AgentStep` from the forced-finalization call with `tool_choice="none"`, not raise an exception or exit silently.
  3. Every `chat.completions.create` call in `loop.py` uses `parallel_tool_calls=False` — verifiable by grepping `loop.py` or by a unit test that inspects the kwargs on each mock call.
  4. A developer can import and call `run_agent_turn` from a plain Python script (no Streamlit context) and iterate the returned generator to completion — confirming the loop is Streamlit-agnostic.
  5. `max_context_tokens=30000` guard triggers forced finalization when cumulative tool-result token count exceeds the cap, verified by an integration test that injects oversized mock tool results.
**Plans**: TBD
**UI hint**: no

### Phase 4: Streaming + Trace UX
**Goal**: `app/pages/home.py` is rewritten to consume the `run_agent_turn` event stream with full live trace UX — `st.status` outer container, `st.write_stream` final answer, `st.expander` trace collapse, SQL in `st.code`, inline Plotly chart — and the old one-shot `pending_sql` flow is fully deleted.
**Depends on**: Phase 3
**Requirements**: UX-01, UX-02, UX-03, UX-04, UX-05, UX-06, UX-07, HOME-01, HOME-02, HOME-03, HOME-04, SAFE-06
**Success Criteria** (what must be TRUE):
  1. Submitting a UFS question on the Home page shows a live `st.status` container with each agent step appearing in real time (tool name, SQL in `st.code`, row count) before the final answer renders — no blank wait screen.
  2. After the final answer renders, a collapsed `st.expander("Show reasoning")` is present and can be reopened by clicking — containing all prior steps including SQL blocks.
  3. The final assistant answer text streams progressively via `st.write_stream` into the chat bubble — it does not appear all at once after a silent pause.
  4. Selecting a non-OpenAI LLM in the sidebar disables the chat input and shows a friendly redirect message pointing to Settings — no agent loop is triggered.
  5. Explorer (`/pages/explorer.py`), Compare (`/pages/compare.py`), and Settings (`/pages/settings_page.py`) pages load and function correctly after the Home rewrite — no import errors, no broken session-state keys, no regressions in their UI.
**Plans**: TBD
**UI hint**: yes

### Phase 5: Test & Polish
**Goal**: The complete focused test suite passes cleanly, the three ship-bar UFS demo scenarios each produce a correct streamed answer with Plotly chart from the seeded database, and the README reflects the new agentic Home flow.
**Depends on**: Phase 4
**Requirements**: SHIP-01, SHIP-02, SHIP-03, HOME-05, TEST-01, TEST-02, TEST-03, TEST-04, TEST-05
**Note on TEST-01 through TEST-05**: These requirements appear in Phase 2 (tool unit tests, TEST-01, TEST-04) and Phase 3 (integration tests, TEST-02, TEST-03, TEST-05) but Phase 5 is the verification gate where the full `pytest` suite is run end-to-end and any gaps are closed. The assignment here reflects the final validation responsibility; the primary implementation phase is noted above.
**Success Criteria** (what must be TRUE):
  1. `pytest app/core/agent/` exits with 0 failures — covering all 6 tool unit tests, the loop integration tests (happy path and budget exhaustion), and the `InfoCategory` grep test.
  2. Manual E2E on the seeded `ufs_data` DB: "Compare `wb_enable` across all devices" returns a final answer with per-device values and renders a bar chart — trace shows `run_sql` → `pivot_to_wide` → `make_chart(bar)`.
  3. Manual E2E: "Which devices have the largest `total_raw_device_capacity`?" returns a ranked list and renders a bar chart — trace shows `run_sql` → `normalize_result` → `make_chart(bar)`.
  4. Manual E2E: "Compare `life_time_estimation_a` for Samsung vs OPPO devices" returns an answer covering both brands and renders a bar or heatmap chart — trace shows `run_sql` → `normalize_result` → `make_chart`.
  5. `logs/queries.log` and `logs/llm.log` each contain correct JSONL entries after the E2E runs — no empty entries, no Python tracebacks embedded in log content, log files remain under a sensible size after 3 test runs.
**Plans**: TBD
**UI hint**: yes

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 0/5 | Not started | - |
| 2. Tool Implementations | 0/TBD | Not started | - |
| 3. Agent Loop Controller | 0/TBD | Not started | - |
| 4. Streaming + Trace UX | 0/TBD | Not started | - |
| 5. Test & Polish | 0/TBD | Not started | - |

---
*Roadmap created: 2026-04-22*
*Last updated: 2026-04-23 after Phase 1 planning (5 plans across 2 waves)*
