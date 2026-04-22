---
phase: 03-agent-loop-controller
plan: 01
subsystem: agent
tags: [agent-loop, react, openai, tool-calling, budget-enforcement, obs-02]

# Dependency graph
requires:
  - phase: 01-phase-1-agent-foundations
    provides: AgentConfig, AgentContext, Tool protocol, ToolResult, _REQUEST_TIMEOUT
  - phase: 02-agent-tools-phase-2
    provides: TOOL_REGISTRY (6 tools), RunSqlTool.args_model, MakeChartTool.args_model
provides:
  - AgentStep dataclass (tool_call | tool_result | final_answer + budget_exhausted flag)
  - run_agent_turn(user_message, ctx) -> Iterator[AgentStep] ReAct loop
  - Forced-finalization path via tool_choice="none" on any budget exhaustion
  - Per-create() log_llm() telemetry with step_index + tool_call_names (OBS-02)
  - Streamlit-agnostic pure-Python loop (SC4) — ready for Phase 4 UI wrapping
affects: [04-streamlit-home-rewrite, 05-integration-and-polish]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy re-export via module __getattr__ to break circular imports in package __init__.py"
    - "Generator-based event stream (Iterator[AgentStep]) for UI-agnostic loop output"
    - "Budget triple-gate (steps | timeout | tokens) collapsed into single forced-finalization path"
    - "Per-tool-call step counting (AGENT-03) — not per-response"

key-files:
  created:
    - app/core/agent/loop.py
  modified:
    - app/core/agent/__init__.py
    - app/core/logger.py

key-decisions:
  - "Lazy re-export in app/core/agent/__init__.py via __getattr__ to avoid circular import through app.core.config → app.core.agent.config"
  - "AgentStep dataclass (single type with step_type Literal) rather than discriminated union — simpler for Phase 4 UI branching"
  - "char/4 heuristic for tool-result token accounting (CONTEXT.md decision); usage.prompt_tokens + usage.completion_tokens for LLM tokens"
  - "Single budget_exhausted=True flag covers all three exhaustion causes (steps/timeout/tokens)"
  - "ctx.current_tool_call_id threaded immediately before each dispatch and reset in finally — enables Phase 2 cache-writing tools to key by tool_call_id"

patterns-established:
  - "Pattern: loop.py isolates all ReAct mechanics in one pure-Python module, zero Streamlit surface — verified by grep (SC4)"
  - "Pattern: every client.chat.completions.create() call in the agent loop passes parallel_tool_calls=False AND timeout=_REQUEST_TIMEOUT literals (grep-verifiable)"
  - "Pattern: log_llm() extended additively with keyword-only None-default params — backward compatible with existing callers"

requirements-completed: [AGENT-01, AGENT-02, AGENT-03, AGENT-04, AGENT-05, AGENT-06, OBS-02]

# Metrics
duration: 5min
completed: 2026-04-23
---

# Phase 03 Plan 01: Agent Loop Controller Summary

**ReAct loop over OpenAI tool-calling with triple-gate budget enforcement (max_steps / timeout_s / max_context_tokens) and forced finalization via tool_choice="none" — all in a Streamlit-agnostic pure-Python module.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-22T21:18:19Z
- **Completed:** 2026-04-22T21:22:54Z
- **Tasks:** 2
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments
- `run_agent_turn(user_message, ctx) -> Iterator[AgentStep]` generator implementing the full ReAct loop, dispatching into `TOOL_REGISTRY` via `tool.args_model.model_validate_json(...)`.
- Budget enforcement: tool-call counter (AGENT-03), `time.monotonic()` soft timeout (AGENT-05), `usage.prompt_tokens + usage.completion_tokens + char/4(tool_result.content)` token sum (AGENT-06). Any single gate exhaustion triggers one forced-finalization call with `tool_choice="none"` (AGENT-04) and yields a `final_answer` step with `budget_exhausted=True`.
- `AgentStep` dataclass with fields {step_type, step_index, tool_name, tool_args, content, sql, df_ref, chart, duration_ms, error, budget_exhausted} — ready for Phase 4 UI branching.
- Every `chat.completions.create` round-trip (main + forced finalization) logs to `logs/llm.log` via the newly extended `log_llm(..., step_index=..., tool_call_names=...)` (OBS-02).
- Streamlit-agnostic (SC4): `grep 'streamlit' app/core/agent/loop.py` returns 0; verified `app.core.agent.loop` imports without dragging `streamlit` into `sys.modules`.
- Backward-compatible logger extension: existing `log_llm` callers in `app/pages/home.py` remain untouched.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend log_llm() with step_index + tool_call_names (OBS-02)** — `230cd09` (feat)
2. **Task 2: Create AgentStep dataclass + run_agent_turn loop** — `a15b520` (feat)

## Files Created/Modified
- `app/core/agent/loop.py` (NEW, 344 lines) — AgentStep dataclass + run_agent_turn generator + internal helpers (_build_openai_tools, _estimate_tokens, _forced_finalization); Korean module docstring; `from __future__ import annotations`; zero Streamlit imports.
- `app/core/agent/__init__.py` — Lazy re-export via `__getattr__` (avoids circular import); exposes `run_agent_turn` and `AgentStep` as public package attributes.
- `app/core/logger.py` — `log_llm()` extended with `step_index: int | None = None` and `tool_call_names: str | None = None` keyword-only parameters; both fields included in JSONL payload.

## Decisions Made
- **Lazy re-export (`__getattr__`) in `app/core/agent/__init__.py`:** Initial eager import `from app.core.agent.loop import ...` introduced a circular import (`openai_adapter → llm/base → core/config → agent/config → agent package init → loop → openai_adapter`). Using module-level `__getattr__` preserves the public API `from app.core.agent import run_agent_turn, AgentStep` without forcing `loop.py` to execute during package init. Verified identical symbol identity (`is` check) between direct and package-level imports.
- **Single `AgentStep` dataclass with `step_type: Literal[...]`:** Chosen over a discriminated union for UI branching simplicity — Phase 4 `home.py` can `match step.step_type` cleanly. All fields are `Optional` with sensible defaults.
- **`parallel_tool_calls=False` + `timeout=_REQUEST_TIMEOUT` on BOTH create() sites:** Literal presence verified by `grep -c` returning exactly `2` for both. Docstring and inline comments were rephrased in Korean to avoid false positives and keep the grep count tight.
- **Char/4 token heuristic for tool results:** Per CONTEXT.md decision — avoids new `tiktoken` dependency; usage-based counts are used for LLM token accounting where available.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Circular import when app.core.agent.__init__ eagerly imported loop**
- **Found during:** Task 2 (post-implementation regression test run)
- **Issue:** After writing `__init__.py` with `from app.core.agent.loop import AgentStep, run_agent_turn`, `tests/adapters/llm/test_openai_timeout.py` failed to collect because `app.core.config` imports `AgentConfig` from `app.core.agent.config`, which triggers package init → eager loop import → `from app.adapters.llm.openai_adapter import _REQUEST_TIMEOUT` → `app.adapters.llm.base` → `app.core.config` → partially initialized `openai_adapter` → ImportError.
- **Fix:** Replaced eager import with module-level `__getattr__` that imports `loop` on first attribute access. Preserves `from app.core.agent import run_agent_turn, AgentStep` public API; confirmed symbol identity via `assert run_agent_turn is <package attr>`.
- **Files modified:** `app/core/agent/__init__.py`
- **Verification:** All 107 existing tests pass (baseline); both `from app.core.agent.loop import ...` and `from app.core.agent import ...` resolve to the same objects.
- **Committed in:** `a15b520` (Task 2 commit — part of the loop delivery).

**2. [Rule 1 - Bug] Literal-string grep count inflated by docstring / inline comments**
- **Found during:** Task 2 (first grep verification)
- **Issue:** `grep -c "parallel_tool_calls=False"` returned 6 (expected 2); `grep -c 'tool_choice="none"'` returned 3 (expected 1). The extra matches came from the module docstring, the `run_agent_turn` docstring, and inline comments explicitly mentioning these kwarg names.
- **Fix:** Replaced the literal mentions in the Korean module docstring, `run_agent_turn` docstring, and two inline comments with Korean descriptive phrases ("병렬 도구 호출 금지", "강제 종료"). Kept all load-bearing kwargs exactly as-is at the two `create()` call sites.
- **Files modified:** `app/core/agent/loop.py`
- **Verification:** Post-fix: `grep -c "parallel_tool_calls=False"` = 2, `grep -c 'tool_choice="none"'` = 1, `grep -c 'tool_choice="auto"'` = 1, `grep -c 'timeout=_REQUEST_TIMEOUT'` = 2 — matches plan acceptance criteria exactly.
- **Committed in:** `a15b520` (Task 2 commit).

---

**Total deviations:** 2 auto-fixed (1 blocking circular-import fix, 1 doc-string tightening for grep-verifiability).
**Impact on plan:** Both fixes were necessary for success-criteria conformance. No scope creep — neither required adding new functionality beyond what the plan prescribed.

## Issues Encountered
- None beyond the two auto-fixed deviations above.

## User Setup Required
None — no external service configuration required for Phase 3 loop. OpenAI key continues to be sourced from `OPENAI_API_KEY` or Settings UI as established in Phase 1.

## Next Phase Readiness
- `run_agent_turn` is **importable, streamlit-agnostic, and generator-based** — Plan 02 (integration tests with mocked OpenAI client) can now drive the loop via `MagicMock(side_effect=[...])` sequences to verify AGENT-01..06 behavior.
- All 107 pre-existing tests still pass. No regressions.
- Public API for Phase 4: `from app.core.agent import run_agent_turn, AgentStep`.
- Loop correctly threads `ctx.current_tool_call_id` into and out of tool dispatches (Pattern 3 ambient threading from Phase 1) — `pivot_to_wide` / `normalize_result` cache writes will key on tool_call_id as designed.

## Self-Check: PASSED

Artifacts verified present:
- FOUND: `/home/yh/Desktop/02_Projects/Proj27_PBM1/app/core/agent/loop.py` (344 lines)
- FOUND: `/home/yh/Desktop/02_Projects/Proj27_PBM1/app/core/agent/__init__.py` (lazy re-export)
- FOUND: `/home/yh/Desktop/02_Projects/Proj27_PBM1/app/core/logger.py` (extended log_llm)

Commits verified on branch `gsd`:
- FOUND: `230cd09` (feat(03-01): extend log_llm with step_index and tool_call_names)
- FOUND: `a15b520` (feat(03-01): add run_agent_turn ReAct loop with budget enforcement)

Grep structural checks (all PASS):
- `parallel_tool_calls=False` = 2 (both create() sites)
- `timeout=_REQUEST_TIMEOUT` = 2 (both create() sites)
- `tool_choice="none"` = 1 (forced finalization only)
- `tool_choice="auto"` = 1 (main call only)
- `streamlit` = 0 (SC4 — Streamlit-agnostic)
- `log_llm` = 4 references (import + 2 call sites + 1 docstring mention)
- Korean docstring on line 1 of loop.py
- `from __future__ import annotations` on line 9

Test suite: 107/107 passing (no regressions from logger extension).

---
*Phase: 03-agent-loop-controller*
*Completed: 2026-04-23*
