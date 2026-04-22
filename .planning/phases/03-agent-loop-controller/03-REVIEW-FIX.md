---
phase: 03-agent-loop-controller
fixed_at: 2026-04-23T00:00:00Z
review_path: .planning/phases/03-agent-loop-controller/03-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 3: Code Review Fix Report

**Fixed at:** 2026-04-23T00:00:00Z
**Source review:** `.planning/phases/03-agent-loop-controller/03-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (0 critical + 3 warning; Info deferred out of scope)
- Fixed: 3
- Skipped: 0

Baseline: 114 tests green. After all three fixes: 115 tests green (one new
regression test added for WR-03). Per-finding `python -m unittest
tests.core.agent.test_loop -v` runs all passed, and the full
`python -m unittest discover tests` run passed with no regressions.

## Fixed Issues

### WR-01: `cumulative_tokens` double-counts prompt history across `create()` calls

**Files modified:** `app/core/agent/loop.py`
**Commit:** `f56d364`
**Applied fix:** Introduced `last_prompt_tokens` sentinel (initialised to 0)
and replaced the `+= prompt_tokens + completion_tokens` accumulator with a
delta-based update: `cumulative_tokens += max(0, current_prompt_tokens -
last_prompt_tokens) + completion_tokens`, then updated `last_prompt_tokens =
current_prompt_tokens`. The `max(0, ...)` guard protects against clients that
occasionally report lower prompt_tokens on a shorter follow-up. Net effect:
cumulative_tokens now tracks `latest_prompt_tokens + Σ completion_tokens + Σ
tool_result_estimates`, which bounds the true wire-token cost rather than an
O(n²) over-count. Updated the inline comment block + the AGENT-06 docstring
line to make the new semantics explicit. `MaxContextTokensTriggersFinalizationTest`
still passes unchanged (5000-byte tool payload still breaches the 1000 cap
after one round-trip), so no test threshold update was needed.

### WR-02: `loop_step_index` semantics drift between `create()` calls and tool events

**Files modified:** `app/core/agent/loop.py`
**Commit:** `01540ca`
**Applied fix:** Followed REVIEW.md option (b) and the orchestrator's
preference: split the single `loop_step_index` into two independent counters.
`llm_call_index` is incremented exactly once per successful `create()`
round-trip (right after `log_llm()` in the main path; the forced-finalization
call consumes the next value) and is the value passed to `log_llm(step_index=
...)` and `_forced_finalization(step_index=...)`. `event_index` is
incremented per yielded `AgentStep` — once for each `tool_call` yield and
once for each `tool_result` yield — and is the value set on `AgentStep.step_index`.
Removed the ambiguous `loop_step_index += 1` that used to bump at the end of
the dispatch loop; the `llm_call_index` is now advanced at its only meaningful
moment (after a successful response is received) and stays consistent across
the budget-check → forced-finalization path. Added inline comments
documenting both counters' contracts. All existing tests rely on step_type
ordering / call_count / kwargs — none inspect step_index values — so no test
change was required.

### WR-03: First-`create()` failure path skips forced finalization

**Files modified:** `app/core/agent/loop.py`, `tests/core/agent/test_loop.py`
**Commit:** `630d9eb`
**Applied fix:** Three changes:
1. Set `budget_exhausted=True` on the early-exit `AgentStep` yielded when
   `error is not None or resp is None`. Per orchestrator directive, this
   unifies the Phase 4 UI's early-termination branch — any final_answer with
   `budget_exhausted=True` now means "the turn was terminated early" regardless
   of whether the cause was a soft-budget trip or a hard API failure. The
   `error` field remains the distinguishing signal between the two
   sub-cases.
2. Expanded the `AgentStep` docstring with an explicit mapping of
   (error, budget_exhausted) tuple → meaning (normal final answer, budget
   forced finalization, loop-level create() failure) so future refactors
   don't accidentally drop the flag.
3. Added `FirstCreateFailureReturnsFinalAnswerTest` in
   `tests/core/agent/test_loop.py` (sibling of
   `ForcedFinalizationOnBudgetExhaustionTest`) asserting exactly one step is
   yielded, `step_type == "final_answer"`, `error` is populated with the
   raised exception message, `budget_exhausted is True`, the content string
   matches `"[loop error: ...]"` format, and `create()` is called exactly
   once (no forced finalization double-call).

---

_Fixed: 2026-04-23_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
