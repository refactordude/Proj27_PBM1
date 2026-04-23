---
phase: 03-agent-loop-controller
plan: 02
subsystem: agent
tags: [integration-tests, agent-loop, mock-openai, budget-enforcement, test-05]

# Dependency graph
requires:
  - phase: 03-agent-loop-controller
    plan: 01
    provides: run_agent_turn, AgentStep, log_llm(step_index, tool_call_names)
provides:
  - Integration test suite for run_agent_turn (mocked OpenAI client)
  - Regression coverage for AGENT-01..06 loop-control semantics
  - Grep + sys.modules dual-mode check for Streamlit-agnostic guarantee (SC4)
  - AGENT-07 stateless-per-turn regression guard
affects: [04-streamlit-home-rewrite, 05-integration-and-polish]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "side_effect=[resp1, resp2, ...] sequence to drive deterministic ReAct loop iterations against a MagicMock OpenAI client"
    - "patch.dict('app.core.agent.loop.TOOL_REGISTRY', {...}, clear=False) — patch the symbol where the loop module imported it, not at the source module, so dispatch sees the replacement"
    - "Fake tool carries the REAL args_model (RunSqlArgs) so tool.args_model.model_validate_json(...) succeeds on synthetic '{\"sql\": \"SELECT 1\"}' payloads"
    - "sys.modules.pop('streamlit', None) + save/restore in finally — verifies loop does not pull streamlit into process via side effects"
    - "TEST-05 discipline: assert on tool-name/kwargs/step-sequence/call-count, never on literal SQL string content"

key-files:
  created:
    - tests/core/agent/test_loop.py
  modified: []

key-decisions:
  - "Used AgentConfig.max_context_tokens=1000 (minimum allowed by ge=1000 validator) rather than the plan's suggested 100; the plan example violated the field bound. Scaled the tool-payload size from 2000 → 5000 chars to keep (~1250 tokens from char/4 + 70 from usage = 1320) ≫ 1000 cap."
  - "Patched TOOL_REGISTRY at app.core.agent.loop (the symbol the loop module imported) instead of at app.core.agent.tools. This is the correct patch site because Python's name resolution binds imports at import time; patching the source module would be invisible to the already-bound loop-module attribute."
  - "Fake tool uses real RunSqlArgs as its args_model (not a MagicMock) because the loop invokes tool.args_model.model_validate_json() — a MagicMock here would silently pass validation and hide real-world failures."
  - "6 TestCase classes (one SC each + AGENT-07 regression) rather than a single class with 6 methods — clearer test-name output and isolates setUp state when it grows in future phases."

patterns-established:
  - "Pattern: Response-factory helpers (_make_tool_call_response / _make_final_answer_response / _make_ctx / _make_fake_run_sql) keep each test body focused on its SC while sharing the MagicMock shape definition in ONE place. Shape changes propagate through 4 helpers, not 7 test bodies."
  - "Pattern: 'Every create() call' assertions iterate call_args_list and carry the index into the assertion message — makes future regression failures pinpoint which create() round-trip drifted."

requirements-completed: [TEST-02, TEST-03, TEST-05]

# Metrics
duration: 3min
completed: 2026-04-23
---

# Phase 03 Plan 02: Integration Tests for run_agent_turn Summary

**Integration-test suite for the ReAct loop using mocked OpenAI clients — 7 tests across 6 TestCase classes covering SC1-SC5 + AGENT-07 regression, with strict TEST-05 discipline (assertions on loop-control, not SQL content).**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-04-22T21:25:58Z
- **Completed:** 2026-04-22T21:28:54Z
- **Tasks:** 1
- **Files created:** 1

## Accomplishments
- `tests/core/agent/test_loop.py` (369 lines, 6 TestCase classes, 7 test methods) — all 7 pass via `python -m unittest tests.core.agent.test_loop -v`.
- **SC1 covered** (`ReactLoopRunSqlThenAnswerTest.test_react_loop_run_sql_then_answer`): drives `side_effect=[tool_call_response, final_answer_response]` and asserts (a) exactly 2 `create()` calls, (b) AgentStep sequence `["tool_call", "tool_result", "final_answer"]`, (c) `tool_name == "run_sql"` on dispatch-relevant steps, (d) final content matches, (e) `budget_exhausted=False` on the clean path.
- **SC2 covered** (`ForcedFinalizationOnBudgetExhaustionTest.test_forced_finalization_on_budget_exhaustion`): feeds 5 consecutive tool-call responses → confirms the 6th `create()` uses `tool_choice="none"` and yields a `final_answer` step with `budget_exhausted=True`. Total `create()` count is exactly 6.
- **SC3 covered** (`ParallelToolCallsFalseEveryCreateTest.test_every_create_call_has_parallel_tool_calls_false`): drives 3 create() round-trips (2 tool + 1 final) and asserts `parallel_tool_calls is False` AND `timeout` kwarg present on EVERY call in `call_args_list`. Carries index into failure messages.
- **SC4 covered** (`StreamlitAgnosticTest`): two tests — (a) static grep of `app/core/agent/loop.py` for `import streamlit` / `from streamlit` (both absent), (b) `sys.modules.pop("streamlit", None)` + run loop + assert streamlit NOT re-added to `sys.modules`. streamlit presence is save/restored in `finally`.
- **SC5 covered** (`MaxContextTokensTriggersFinalizationTest.test_oversized_tool_result_triggers_forced_finalization`): uses `max_context_tokens=1000` + 5000-char tool-result payload (char/4 heuristic → 1250 tokens + 70 usage = 1320 tokens ≫ 1000 cap) → forces `tool_choice="none"` on the 2nd `create()` call.
- **AGENT-07 regression** (`StatelessPerTurnTest.test_fresh_context_per_turn_distinct_df_caches`): constructs two distinct `AgentContext` instances, populates `ctx1._df_cache["call_ghost"]`, runs both turns, asserts `ctx1._df_cache is not ctx2._df_cache` and `"call_ghost" not in ctx2._df_cache`.
- **TEST-05 discipline verified**: `grep 'assert.*== "SELECT' tests/core/agent/test_loop.py` → 0 matches. Only type/presence checks on `steps[0].sql`.
- **No regressions**: full suite `python -m unittest discover tests/` reports 114/114 passing (107 previous + 7 new).

## Task Commits

1. **Task 1: Write tests/core/agent/test_loop.py with 7 integration tests covering SC1-SC5 + AGENT-07 regression** — `b22076c` (test)

## Files Created/Modified
- `tests/core/agent/test_loop.py` (NEW, 369 lines) — stdlib `unittest` module with zero pytest imports, zero actual `import streamlit` statements (though the string "streamlit" appears in test identifiers, comments, and `assertNotIn("streamlit", ...)` negative checks which are required by SC4's own test logic). Uses `MagicMock` + `patch.dict` exclusively for OpenAI/tool mocking.

## Decisions Made
- **`max_context_tokens=1000` (plan suggested 100)**: `AgentConfig` imposes `ge=1000` on this field, so the plan's example value of 100 raised `ValidationError` at test setup time. Chose the minimum allowed value (1000) and scaled the mock tool-payload from 2000 → 5000 chars so (char/4 = 1250) + (prompt+completion usage = 70) = 1320 tokens comfortably exceeds the 1000 cap. SC5 semantics (oversized tool_result triggers forced-finalization via `tool_choice="none"`) are fully preserved.
- **Patch site `app.core.agent.loop.TOOL_REGISTRY`, not `app.core.agent.tools`**: Python binds imports at import time, so the `loop.py` module holds its own reference named `TOOL_REGISTRY` that points to the original dict. Patching the source module (`app.core.agent.tools.TOOL_REGISTRY`) would leave the loop's bound reference untouched. `patch.dict` with `clear=False` preserves the other 5 real tools and only overrides `run_sql` for safety.
- **Fake tool carries real `RunSqlArgs` class as `args_model`**: The loop calls `tool.args_model.model_validate_json(raw_args or "{}")`. If `args_model` were a plain `MagicMock`, `model_validate_json` would return a MagicMock and silently succeed on garbage input — hiding regressions. Using the real Pydantic class means validation does real JSON parsing against the real schema and can catch future breakage.
- **6 TestCase classes instead of a single class with 6 methods**: Clearer `unittest -v` output (each SC gets its own fully-qualified path), isolates any future `setUp`/`tearDown` growth, and matches the style of the existing `tests/core/agent/test_config.py` (`AgentConfigDefaultsTest`, `AgentConfigBoundsTest`, `AgentConfigInstanceIndependenceTest`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Plan example `max_context_tokens=100` violates AgentConfig `ge=1000` bound**
- **Found during:** Task 1 first test run (`python -m unittest tests.core.agent.test_loop -v`).
- **Issue:** The plan's Test 4 body specified `_make_ctx(max_context_tokens=100)` but `AgentConfig.max_context_tokens` is declared `Field(default=30_000, ge=1000, le=1_000_000)` (as verified in Plan 01 / `app/core/agent/config.py` and in `tests/core/agent/test_config.py::test_max_context_tokens_too_low`). Construction raised `pydantic_core._pydantic_core.ValidationError: Input should be greater than or equal to 1000`.
- **Fix:** Used `max_context_tokens=1000` (the minimum allowed) and scaled the big-payload from 2000 chars → 5000 chars so the char/4 heuristic (1250 tokens) + usage tokens (70) = 1320 still comfortably exceed the 1000 cap. SC5 contract (oversized tool_result triggers forced finalization) fully preserved.
- **Files modified:** `tests/core/agent/test_loop.py` (single test body only).
- **Verification:** Post-fix, 7/7 tests pass; `MaxContextTokensTriggersFinalizationTest` confirms `tool_choice="none"` on the 2nd `create()` call and `budget_exhausted=True` on the yielded step.
- **Committed in:** `b22076c` (Task 1 commit).

---

**Total deviations:** 1 auto-fixed (blocking — plan example parameter violated Phase 1 validation bound).
**Impact on plan:** Semantic intent of SC5 (oversized tool_result forces finalization) fully preserved; only the parameter value was adjusted to satisfy the validator.

## Issues Encountered
- None beyond the single auto-fixed bound violation above.

## User Setup Required
None — all OpenAI interaction is mocked via `MagicMock.side_effect`. No network, no credentials, no services.

## Next Phase Readiness
- Phase 4 UI rewrite can consume `run_agent_turn(user_message, ctx) -> Iterator[AgentStep]` with full confidence that the loop's contract is regression-tested:
  - Step sequence ordering is stable.
  - Budget-exhaustion paths collapse into a single `tool_choice="none"` forced-finalization regardless of which gate (steps/tokens) tripped.
  - Every `create()` call carries `parallel_tool_calls=False` + `timeout` kwarg.
  - `_df_cache` is per-turn, not per-process.
- Full suite green: **114/114 passing** (was 107 before this plan). No regressions.

## Self-Check: PASSED

Artifacts verified present:
- FOUND: `/home/yh/Desktop/02_Projects/Proj27_PBM1/tests/core/agent/test_loop.py` (369 lines, ≥250 min_lines)

Commits verified on branch `gsd`:
- FOUND: `b22076c` (test(03-02): add integration tests for run_agent_turn covering SC1-SC5 + AGENT-07)

Structural grep checks (all PASS):
- `import pytest` / `from pytest` in test file = 0
- actual `import streamlit` / `from streamlit` statements (anchored) = 0 (14 string-literal/identifier/docstring references, all required by SC4 test logic)
- `unittest.TestCase` classes = 6 (as required by plan)
- `MagicMock` usages = 20
- literal-SQL assertions (`assert ... == "SELECT...`) = 0 (TEST-05 discipline)
- `class ReactLoopRunSqlThenAnswerTest` present = yes (required by must_haves.artifacts.contains)

Test execution:
- `python -m unittest tests.core.agent.test_loop -v` → **Ran 7 tests in 1.059s / OK**
- `python -m unittest discover tests/` → **Ran 114 tests in 4.003s / OK** (107 → 114, +7 new, 0 regressions)

---
*Phase: 03-agent-loop-controller*
*Completed: 2026-04-23*
