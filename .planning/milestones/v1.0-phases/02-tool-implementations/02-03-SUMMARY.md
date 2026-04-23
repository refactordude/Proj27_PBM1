---
phase: 02-tool-implementations
plan: 03
subsystem: agent-tools
tags: [pivot_to_wide, pandas, pivot_table, aggfunc, dataframe-cache, tool_call_id, pydantic, ufs]

# Dependency graph
requires:
  - phase: 01-agent-scaffold
    provides: "AgentContext dataclass with _df_cache + store_df/get_df; Tool Protocol; ToolResult model; AgentConfig with row_cap/allowed_tables"
provides:
  - "AgentContext.current_tool_call_id: str | None = None (Pattern 3 ambient threading slot)"
  - "pivot_to_wide_tool — TOOL-03 long→wide pivot with aggfunc='first' de-dup"
  - "PivotToWideArgs (Pydantic BaseModel) exposing category + item via model_json_schema for TOOL-07"
  - "Cache-write path: wide DF stored in ctx._df_cache keyed by current_tool_call_id (uuid fallback)"
  - "Empty-result friendly-message path with df_ref=None (no cache write)"
affects: [02-04-normalize_result, 02-06-make_chart, 02-07-registry, 03-agent-loop]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pattern 3 ambient tool_call_id threading on AgentContext (keeps args_model JSON schema clean for OpenAI)"
    - "Tool classes follow Phase 1 Protocol structurally (name, args_model, __call__) — no inheritance"
    - "Code-generated parametrized SQL with single-quote doubling escape (v1 acceptable under Pydantic-validated closed allowlist — Assumption A2)"
    - "DataFrame cache key = current_tool_call_id or uuid4().hex fallback (supports standalone unit-testing without a loop)"

key-files:
  created:
    - app/core/agent/tools/pivot_to_wide.py
    - tests/core/agent/tools/test_pivot_to_wide.py
    - tests/core/agent/test_context_tool_call_id.py
  modified:
    - app/core/agent/context.py

key-decisions:
  - "Use aggfunc='first' in df.pivot_table to silently collapse duplicate (parameter, PLATFORM_ID) pairs — contractual per CONTEXT.md and RESEARCH.md Pitfall 3"
  - "Land current_tool_call_id in Phase 2 (not Phase 3) per RESEARCH.md Assumption A4 — non-breaking dataclass addition, unblocks cache-key unit tests"
  - "Fallback to uuid4().hex when current_tool_call_id is None so pivot_to_wide can be unit-tested without a loop controller"
  - "Empty DataFrame path returns ToolResult(content='No rows matched …', df_ref=None) — no cache write, so downstream tools get an explicit null df_ref"
  - "Single-quote SQL escape via s.replace(\"'\", \"''\") — acceptable v1 per Assumption A2 (closed allowlist + Pydantic-typed args); v2 HARD-07 covers parameterized binding"

patterns-established:
  - "Ambient threading via AgentContext fields (not args_model fields) for loop-layer concerns like tool_call_id"
  - "Tool-local helper functions prefixed with _ (e.g., _sql_escape) keep module surface minimal"
  - "Fallback-to-uuid pattern for tool_call_id-keyed caches when running without a loop controller"

requirements-completed: [TOOL-03, TOOL-07]

# Metrics
duration: ~10 min
completed: 2026-04-23
---

# Phase 2 Plan 3: pivot_to_wide Tool + AgentContext current_tool_call_id Summary

**TOOL-03 pivot_to_wide tool reshapes long-form ufs_data into a wide per-PLATFORM_ID DataFrame via `df.pivot_table(aggfunc='first')`, caches it in `AgentContext._df_cache`, and returns `df_ref` — plus the non-breaking AgentContext.current_tool_call_id ambient-threading slot that unblocks this and downstream cache-key tests.**

## Performance

- **Duration:** ~10 min
- **Tasks:** 4 (all completed sequentially on main working tree)
- **Files modified:** 4 (1 modified, 3 created)
- **Test count delta:** +12 tests (4 context tool_call_id + 8 pivot_to_wide); whole agent dir now 52 tests, all green

## Accomplishments

- AgentContext gained a single optional `current_tool_call_id: str | None = None` field (Pattern 3 ambient threading) — non-breaking; all 4 Phase 1 context tests still pass.
- `pivot_to_wide_tool` implements TOOL-03 end-to-end: code-generated parametrized SELECT on ufs_data, `pivot_table(aggfunc='first')` reshape, cache write, df_ref return.
- 8 unit tests cover happy path + aggfunc='first' domain-edge (TEST-01 leg for TOOL-03) + Pydantic validation + empty-result friendly path + uuid fallback + SQL escape + Protocol compliance.
- 4 regression tests cover the new `current_tool_call_id` field (default, constructor override, post-construction mutability, instance isolation).
- SAFE-07 compliant across all new and modified files: no correctly-spelled `InfoCategory` anywhere in this plan's surface.

## Task Commits

1. **Task 1: Extend AgentContext with current_tool_call_id** — `1a8efa9` (feat)
2. **Task 2: Create context tool_call_id regression test** — `fb5342a` (test)
3. **Task 3: Create pivot_to_wide.py tool module** — `60240db` (feat)
4. **Task 4: Create test_pivot_to_wide.py** — `2d22eb3` (test)

## Files Created/Modified

- `app/core/agent/context.py` — Added `current_tool_call_id: str | None = None` between `config` and `_df_cache`; updated module docstring with Pattern 3 rationale. Single-line additive change.
- `app/core/agent/tools/pivot_to_wide.py` — New: `PivotToWideArgs` (Pydantic), `PivotToWideTool` class satisfying Tool Protocol, module-level `pivot_to_wide_tool` singleton, `_sql_escape` helper.
- `tests/core/agent/tools/test_pivot_to_wide.py` — New: 8 unittest TestCases covering happy path, aggfunc='first' dedup, Pydantic validation (missing args), empty result path, uuid fallback, SQL single-quote escape, Protocol compliance.
- `tests/core/agent/test_context_tool_call_id.py` — New: 4 unittest TestCases covering default None, constructor override, post-construction mutability, instance-level isolation.

## Decisions Made

- **aggfunc='first' is the contract, not a bug** — verified via RESEARCH.md Pitfall 3 and explicitly codified in TEST-01 domain-edge test `PivotAggfuncFirstDedupTest.test_duplicate_key_kept_first`.
- **current_tool_call_id lands in Phase 2 (not Phase 3)** per RESEARCH.md Assumption A4 — non-breaking dataclass addition unblocks cache-key unit tests without awkward `**kwargs` workarounds.
- **uuid.uuid4().hex fallback** when `ctx.current_tool_call_id` is None — lets the tool be unit-tested without a loop controller, and makes the behavior explicit and deterministic-within-a-call.
- **SQL single-quote escape via `s.replace(\"'\", \"''\")`** — acceptable v1 per Assumption A2 (closed allowlist + Pydantic-typed args come from OpenAI function-calling, not user free-text). v2 HARD-07 covers parameterized binding.
- **Empty-result path returns `df_ref=None`** so downstream tools (`normalize_result`, `make_chart`) can detect "no data" without a cache lookup.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0
**Impact on plan:** Clean execution — all tasks performed verbatim per PLAN.md actions/acceptance-criteria. No deviation rules triggered.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-04 (`normalize_result`) can now:
  - Read `ctx.current_tool_call_id` as cache key.
  - Accept a `data_ref` arg, `ctx.get_df(data_ref)` to read the pivot_to_wide output, apply UFS spec §5 normalization, and write back via `ctx.store_df(new_key, normalized)`.
- Plan 02-06 (`make_chart`) can read `data_ref` from cache the same way.
- Plan 02-07 (TOOL_REGISTRY) will import `pivot_to_wide_tool` — the singleton is already exported from `app.core.agent.tools.pivot_to_wide`.
- Phase 3's loop controller is responsible for setting `ctx.current_tool_call_id` before each tool dispatch; the slot exists, defaulted, mutable, and instance-local.

## Self-Check: PASSED

- `app/core/agent/context.py` exists, contains `current_tool_call_id: str | None = None`
- `app/core/agent/tools/pivot_to_wide.py` exists
- `tests/core/agent/tools/test_pivot_to_wide.py` exists (8 tests passing)
- `tests/core/agent/test_context_tool_call_id.py` exists (4 tests passing)
- Commits `1a8efa9`, `fb5342a`, `60240db`, `2d22eb3` present in `git log`
- `python -m unittest tests.core.agent.tools.test_pivot_to_wide tests.core.agent.test_context_tool_call_id -v` → Ran 12 tests, OK
- `python -m unittest discover -s tests/core/agent` → Ran 52 tests, OK (no Phase 1/2 regressions)
- `grep -rE 'InfoCategory\b'` over all files in this plan → 0 matches (SAFE-07 clean)

---
*Phase: 02-tool-implementations*
*Plan: 03*
*Completed: 2026-04-23*
