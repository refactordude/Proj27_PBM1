---
name: Phase 5 Test & Polish Context
description: Final phase — full test suite green, 3 ship-bar E2E scenarios exercised via mocked DB adapter, log sanity, README updated to reflect agentic Home flow.
phase: 5
status: ready_for_planning
mode: locked_requirements_skip
---

# Phase 5: Test & Polish - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning
**Mode:** Smart discuss skipped — scope and acceptance criteria are fully locked by REQUIREMENTS.md (SHIP-01..03, HOME-05, TEST-01..05).

<domain>
## Phase Boundary

The complete focused test suite passes cleanly, the three ship-bar UFS demo scenarios each produce a correct streamed answer with Plotly chart from the seeded database, and the README reflects the new agentic Home flow.

**In-scope deliverables:**

- **SC1 / TEST-01..05 aggregate:** `python -m unittest discover tests` exits 0 across all 121+ Phase 1-4 tests + any Phase 5 additions.
- **SC2 / SHIP-01:** E2E scenario "Compare `wb_enable` across all devices" — mocked DB adapter returns representative seeded rows; the full `run_agent_turn` loop dispatches `run_sql` → `pivot_to_wide` → `make_chart(bar)` and emits a final-answer AgentStep with non-empty text and a Plotly bar Figure on a prior step.
- **SC3 / SHIP-02:** E2E scenario "Which devices have the largest `total_raw_device_capacity`?" — mocked DB returns rows whose Result field contains hex + decimal values; loop dispatches `run_sql` → `normalize_result` → `make_chart(bar)` and yields a ranked list + bar chart.
- **SC4 / SHIP-03:** E2E scenario "Compare `life_time_estimation_a` for Samsung vs OPPO devices" — mocked DB returns two-brand rows; loop dispatches `run_sql` → `normalize_result` → `make_chart` (bar or heatmap).
- **SC5 / Log sanity:** Inspect `logs/queries.log` and `logs/llm.log` entries written during the E2E tests. Validate each line is well-formed JSONL (`json.loads` succeeds), contains required fields, contains zero Python tracebacks or multi-line payloads.
- **HOME-05:** Explorer, Compare, Settings pages load without error. Check via AST parse + import smoke on each module (full Streamlit runtime check deferred to the user's manual acceptance).
- **README update:** `README.md` reflects the new agentic Home flow — removes any stale "generate SQL, confirm, execute" language; adds a section describing the agentic Q&A UX and OpenAI-only v1 constraint.

**Live-DB validation (SHIP-01/02/03 per the literal REQUIREMENTS.md text):**
The ROADMAP requires these to run against the seeded `ufs_data` database. Automated CI cannot reach that DB from this environment. Phase 5 delivers MOCKED-DB equivalents that exercise the entire code path end-to-end — the only missing piece is real MySQL data. That manual validation step is surfaced as `status: human_needed` in the Phase 5 VERIFICATION.md so the operator runs `streamlit run app/main.py` against the live DB before shipping.

**Out of scope:**
- Backfilling tests for existing non-agent modules (sql_safety regex, adapters, auth) — HARD-01 v2 backlog.
- Log rotation (HARD-02 v2).
- Cost / token dashboard (HARD-06 v2).

</domain>

<decisions>
## Implementation Decisions

### Locked by REQUIREMENTS.md
- E2E tests use `unittest.mock.MagicMock` for BOTH the OpenAI client AND the DB adapter. The OpenAI client's `chat.completions.create` is given a `side_effect=[<tool_call_response>, <tool_call_response>, <text_response>]` matching the expected tool sequence for each scenario. The DB adapter's `run_query(sql)` is stubbed with a `side_effect` returning a specific `pd.DataFrame` fixture per call.
- Fixtures live in `tests/fixtures/ufs_seed.py` (NEW) — small helper module exporting callable builders: `wb_enable_rows()`, `capacity_rows()`, `lifetime_samsung_oppo_rows()`. Each returns a pandas DataFrame with the long-form `(PLATFORM_ID, InfoCatergory, Item, Result)` columns matching the UFS schema.
- Each E2E test asserts: the tool dispatch ORDER (via inspection of yielded AgentSteps), final-answer AgentStep is present with non-empty text, chart AgentStep is present with a plotly.graph_objects.Figure, and no raw Python tracebacks appear in the content.
- Log sanity check: open `logs/queries.log` + `logs/llm.log` (if they exist — tests MAY create them), iterate line-by-line, assert `json.loads(line)` succeeds on each, assert no line contains `'Traceback'` or starts with a non-JSON character.
- README update: rewrite the "Usage" section (or equivalent) to describe the agentic Q&A flow. Remove any reference to SQL preview/edit. Add a 2-sentence OpenAI-only v1 caveat.

### Conventions
- stdlib `unittest` + `unittest.mock` (no pytest dep).
- Korean docstrings on new modules where the project uses Korean; English in test files is fine.
- `from __future__ import annotations`.

### Claude's Discretion
- **Fixture row counts:** Small (2-8 devices per scenario) — just enough to exercise pivot/normalize + rendering without making tests slow.
- **README content tone:** Match existing README style (Korean or English — whichever the current README uses).

</decisions>

<code_context>
### Reusable Assets (from Phase 1-4)
- `app.core.agent::run_agent_turn, AgentStep` — the public API.
- `app.core.agent.tools::TOOL_REGISTRY` — dispatch target.
- `app.core.agent.context::AgentContext` — constructed per turn; tests build a lightweight ctx with MagicMock adapters.
- `app.core.agent.config::AgentConfig` — default budgets.
- `app.core.logger::log_query, log_llm` — write JSONL that SC5 validates.

### Integration Points
- `tests/e2e/test_ship_bar.py` (NEW) — houses the 3 SHIP scenarios + log sanity test.
- `tests/fixtures/ufs_seed.py` (NEW, small) — fixture builders.
- `README.md` (MODIFIED) — small section rewrite.

</code_context>

<specifics>
## Specific Ideas

- **Mocked OpenAI response shape per scenario** — each tool-call response needs an `id`, `function.name`, `function.arguments` (JSON string). Use a helper `_mock_tool_call_response(tool_name, args_dict)` to reduce boilerplate.
- **Chart detection** — iterate steps, find one where `step.chart is not None` and `isinstance(step.chart, plotly.graph_objects.Figure)`.
- **Final answer presence** — last step must have `step_type == "final_answer"` and `step.content` non-empty.
- **Tool sequence match** — filter steps by `step_type == "tool_call"` and assert `[s.tool_name for s in tool_calls] == ["run_sql", "pivot_to_wide", "make_chart"]` (for SHIP-01) etc.
- **Log sanity helper** — `_assert_jsonl_clean(path)` opens the file, reads lines, parses each with `json.loads`, asserts no `Traceback` substring in any line, asserts file size < 1MB.

</specifics>

<deferred>
## Deferred Ideas

- **Live-DB E2E CI run** — requires infrastructure; manual for now.
- **Test backfill for non-agent modules** — HARD-01 v2 backlog.

</deferred>
