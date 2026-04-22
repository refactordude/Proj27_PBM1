---
phase: 01-foundation
plan: 04
subsystem: adapters-llm
tags: [openai, httpx, timeout, safety, agent-08]

# Dependency graph
requires: []
provides:
  - "_REQUEST_TIMEOUT = httpx.Timeout(30.0) module-level constant in app/adapters/llm/openai_adapter.py"
  - "timeout kwarg wired onto both chat.completions.create call sites (generate_sql + stream_text)"
  - "Unit-test contract (tests/adapters/llm/test_openai_timeout.py) guarding both call sites against future regression"
affects: [03-agent-loop, 04-home-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-request httpx.Timeout via a DRY module-level constant (not client-constructor timeout)"
    - "Mock-based unittest assertion on call_args.kwargs for kwarg passthrough verification"

key-files:
  created:
    - tests/adapters/__init__.py
    - tests/adapters/llm/__init__.py
    - tests/adapters/llm/test_openai_timeout.py
  modified:
    - app/adapters/llm/openai_adapter.py

key-decisions:
  - "Used httpx.Timeout(30.0) object (not bare float) per CONTEXT.md lock — explicit, uniform across connect/read/write/pool"
  - "Placed constant at module level (not in _client()) so both generate_sql and stream_text share the same instance — unit tests can assert kwargs[\"timeout\"] is _REQUEST_TIMEOUT"
  - "Did NOT move timeout onto OpenAI() constructor — per-request override preserves Phase 3 agent-loop flexibility for tuning read timeouts separately"

patterns-established:
  - "OpenAI adapter call-site timeout pattern: import httpx + _REQUEST_TIMEOUT constant + timeout=_REQUEST_TIMEOUT kwarg on every chat.completions.create call"
  - "Adapter unit-test layout: tests/adapters/<category>/test_<feature>.py using stdlib unittest + MagicMock + patch.object(_client)"

requirements-completed: [AGENT-08]

# Metrics
duration: 2m 15s
completed: 2026-04-23
---

# Phase 01 Plan 04: OpenAI Adapter Timeout Summary

**30-second httpx.Timeout wired onto every OpenAI chat.completions.create call via a DRY module-level constant, bounding all four network phases (connect/read/write/pool) and closing the indefinite-hang vector on both generate_sql and stream_text.**

## Performance

- **Duration:** 2m 15s
- **Started:** 2026-04-22T16:03:19Z
- **Completed:** 2026-04-22T16:05:34Z
- **Tasks:** 2
- **Files modified:** 1
- **Files created:** 3

## Accomplishments

- AGENT-08 fully satisfied: OpenAI API hangs are now bounded by a 30-second timeout across all phases (connect / read / write / pool)
- `_REQUEST_TIMEOUT = httpx.Timeout(30.0)` constant added at module level in `app/adapters/llm/openai_adapter.py`; shared by both call sites (generate_sql and stream_text)
- Korean module docstring extended with the AGENT-08 citation line while preserving all prior content
- SC4 coverage in place: 3 stdlib-unittest tests verify the constant shape AND kwarg passthrough on both call paths, guarding against a future SDK-level timeout-drop regression (see RESEARCH § Pitfall 3, openai#322 history)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add httpx.Timeout to openai_adapter.py — both call sites** — `8cf38b3` (feat)
2. **Task 2: Create tests/adapters/llm/test_openai_timeout.py — SC4 coverage** — `b0e67f7` (test)

_Note: Task 1 is marked `tdd=true` in the plan, but its verification test lives in Task 2 per the plan's split (the test module is created once in Task 2 and covers Task 1's four edits). Tests pass after both commits land — 3/3 OK._

## Files Created/Modified

- `app/adapters/llm/openai_adapter.py` — Extended Korean docstring (AGENT-08 line added); added `import httpx` in third-party import block; added module-level `_REQUEST_TIMEOUT = httpx.Timeout(30.0)` between imports and class definition; appended `timeout=_REQUEST_TIMEOUT` kwarg to both `chat.completions.create` calls. `_client()` / `OpenAI()` constructor is intentionally unchanged.
- `tests/adapters/__init__.py` — New empty package root for adapter unit tests.
- `tests/adapters/llm/__init__.py` — New empty package root for LLM-adapter unit tests.
- `tests/adapters/llm/test_openai_timeout.py` — New test module with 3 `unittest.TestCase` classes: `RequestTimeoutConstantTest` (shape of `_REQUEST_TIMEOUT`), `GenerateSqlTimeoutTest` (kwarg passthrough), `StreamTextTimeoutTest` (kwarg passthrough + `stream=True`).

## Decisions Made

- **Object-form timeout over float.** Followed the CONTEXT.md lock: `httpx.Timeout(30.0)` not bare `timeout=30.0`. With a single positional arg, httpx uniformly bounds connect/read/write/pool — verified at import time and in `RequestTimeoutConstantTest`.
- **Module-level constant, not `_client()`-local.** A single `_REQUEST_TIMEOUT` instance is shared by both call sites, and the same object identity is what the unit tests assert via `assertIs`. Placing it in `_client()` would rebuild the Timeout each call and break `assertIs`-based contract tests.
- **Per-request kwarg, not client-constructor.** Leaves Phase 3's agent loop free to override read timeouts per call (e.g., longer for large `tools` calls) without retrofitting the adapter.
- **Did not propagate to `app/adapters/llm/base.py` or Ollama adapter.** Ollama has its own HTTP layer via `requests`; the LLM `base` class is an ABC and shouldn't carry implementation-specific transport constants.

## Deviations from Plan

None — plan executed exactly as written. Plan spec for all four edits (docstring, imports+constant, generate_sql, stream_text) applied verbatim; test module content matches the plan's inline blueprint character-for-character.

One pre-execution environment setup occurred: `.venv/` was missing `openai` and `httpx`, so both were `pip install`ed into the venv (both are already pinned in `requirements.txt` — no new dependency added, venv was just stale). The sequential_execution prompt block explicitly pre-authorized this.

## Issues Encountered

None. All 8 Task-1 acceptance criteria, 11 Task-2 acceptance criteria, and 4 plan-level success criteria passed on first execution.

## User Setup Required

None — no external service configuration required. The timeout wiring is transparent to operators; no `.env` changes, no `settings.yaml` changes.

## Next Phase Readiness

- **Ready for Phase 3 agent loop:** the agent controller can reuse the exact same `OpenAIAdapter` instance — every `chat.completions.create` invocation is already bounded, so the loop's per-turn `timeout_s=30` budget has a matching transport-level guarantee.
- **Ready for Phase 2 tools plan:** no blockers. This plan touched only `openai_adapter.py` and a new test tree — Wave-1 parallel-safe with plans 01/02/03.
- **Regression net:** `python -m unittest tests.adapters.llm.test_openai_timeout` runs in ~13ms; wire into any future CI smoke step cheaply.

## Self-Check

**Files claimed exist:**
- FOUND: app/adapters/llm/openai_adapter.py
- FOUND: tests/adapters/__init__.py
- FOUND: tests/adapters/llm/__init__.py
- FOUND: tests/adapters/llm/test_openai_timeout.py

**Commits claimed exist:**
- FOUND: 8cf38b3 (Task 1)
- FOUND: b0e67f7 (Task 2)

**Success criteria re-verified post-write:**
- `grep -c '_REQUEST_TIMEOUT' app/adapters/llm/openai_adapter.py` = 3 (≥3 required)
- `grep -c 'httpx.Timeout(30.0)' app/adapters/llm/openai_adapter.py` = 1 (≥1 required)
- `grep -c 'timeout=_REQUEST_TIMEOUT' app/adapters/llm/openai_adapter.py` = 2
- `head -1 app/adapters/llm/openai_adapter.py` contains Korean (`OpenAI LLM 어댑터`)
- `python -m unittest tests.adapters.llm.test_openai_timeout -v` → 3 tests, all OK

## Self-Check: PASSED

---
*Phase: 01-foundation*
*Plan: 04*
*Completed: 2026-04-23*
