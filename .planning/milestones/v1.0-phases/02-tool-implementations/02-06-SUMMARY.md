---
phase: 02-tool-implementations
plan: 06
subsystem: agent-tools
tags: [plotly, plotly-express, pydantic, visualization, agent-tool, TOOL-06, TOOL-07]

# Dependency graph
requires:
  - phase: 01-agent-foundation
    provides: Tool Protocol, ToolResult (arbitrary_types_allowed), AgentContext._df_cache
provides:
  - make_chart_tool singleton (TOOL-06) — 6th and final Wave 1 tool
  - MakeChartArgs Pydantic model (TOOL-07 schema-ready)
  - plotly.express-based bar/line/scatter/heatmap routing on plotly 6.7.0
  - test_make_chart with 8 tests covering 4 chart types + validation + missing-ref
affects: [02-07-registry, 03-agent-loop, 04-ui-render]

# Tech tracking
tech-stack:
  added: []  # no new pip deps; plotly.express already pinned
  patterns:
    - "Tool class with class-level name/args_model + __call__ (structural Tool Protocol conformance)"
    - "Errors returned as ToolResult(content=<msg>, chart=None) instead of raised exceptions"
    - "px.imshow(df) for heatmap — DataFrame used directly; index=y, columns=x"

key-files:
  created:
    - app/core/agent/tools/make_chart.py
    - tests/core/agent/tools/test_make_chart.py
  modified: []

key-decisions:
  - "Chose plotly.express (px.bar/line/scatter/imshow) over plotly.graph_objects per CONTEXT.md Claude's Discretion — brevity wins; all four chart types supported cleanly on plotly 6.7.0."
  - "Heatmap branch ignores x/y/color args per RESEARCH.md — px.imshow(df) uses the DataFrame index/columns as axis labels; passing x/y would double-specify."
  - "try/except around px calls converts plotly argument errors (e.g., missing x when required) to ToolResult(content='make_chart error: ...') — matches Phase 1 tool error contract (never raise to loop controller)."

patterns-established:
  - "Plotly-returning tools set ToolResult.chart=<Figure>; content remains a 1-line summary string for the model"
  - "AgentContext test construction uses MagicMock helper (_mk_ctx) with required positional args — reusable across tool tests"

requirements-completed: [TOOL-06, TOOL-07]

# Metrics
duration: 2min
completed: 2026-04-23
---

# Phase 02 Plan 06: make_chart Tool Summary

**TOOL-06 `make_chart` implemented via plotly.express — Literal-validated chart_type (bar/line/scatter/heatmap), cache-backed DataFrame lookup, and Plotly Figure returned in ToolResult.chart for Phase 4 UI rendering.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-22T20:32:25Z
- **Completed:** 2026-04-22T20:34:26Z
- **Tasks:** 2
- **Files modified:** 2 (both created)

## Accomplishments
- `MakeChartArgs` Pydantic model with `Literal["bar","line","scatter","heatmap"]` chart_type — Pydantic rejects `"pie"` before the tool runs
- `MakeChartTool.__call__` routes to the correct `px.*` function per chart_type and returns `ToolResult(chart=<Figure>, content=<summary>)`
- Missing `data_ref` returns `ToolResult(content="make_chart error: data_ref '...' not found in cache")` — never raises
- Heatmap branch uses `px.imshow(df)` — DataFrame index = y-axis, columns = x-axis
- 8 unit tests green: 4 chart-type happy paths + Tool Protocol check + 2 Pydantic validation rejects + 1 missing-ref edge
- Full suite: 87 tests pass (no regressions from prior 5 Wave 1 plans)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement make_chart tool module** — `00ce153` (feat)
2. **Task 2: Unit tests for make_chart** — `015884e` (test)

_Note: Plan ordered module-first, tests-second; the `tdd="true"` flag is honored by running tests immediately after write rather than RED-before-GREEN (tool module has no preceding code to test against)._

## Files Created/Modified
- `app/core/agent/tools/make_chart.py` — MakeChartArgs + MakeChartTool + make_chart_tool singleton (62 lines)
- `tests/core/agent/tools/test_make_chart.py` — 8 tests across 3 TestCase classes (130 lines)

## Decisions Made
- **plotly.express over plotly.graph_objects** for all 4 chart types. CONTEXT.md gave Claude's discretion; RESEARCH.md verified `px.bar/line/scatter/imshow` on plotly 6.7.0. Result is ~5 lines of routing logic vs. ~30 with `go.Figure(go.Bar(...))`.
- **Heatmap ignores x/y/color** — `px.imshow(df)` uses the DataFrame directly. Forwarding x/y would require a different API (`px.imshow(img, x=cols, y=rows)`) and contradict the "pivoted matrix IS the data layout" contract.
- **Error strings prefixed `"make_chart error:"`** so Phase 3's loop controller can surface them cleanly and the model can distinguish tool errors from tool output.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Adapted AgentContext construction in tests to pass required kwargs**
- **Found during:** Task 2 (Unit tests for make_chart)
- **Issue:** Plan's test code used `AgentContext()` with no arguments, but `AgentContext` is a dataclass with 5 required positional fields: `db_adapter`, `llm_adapter`, `db_name`, `user`, `config`. Running the plan verbatim would fail with `TypeError: AgentContext.__init__() missing 5 required positional arguments`.
- **Fix:** Introduced a `_mk_ctx()` helper that constructs `AgentContext` with `MagicMock()` db/llm adapters, `db_name="unit_db"`, `user="alice"`, and `AgentConfig()`. This matches the established pattern in `tests/core/agent/tools/test_pivot_to_wide.py` and `test_normalize_result.py` from prior plans in this phase.
- **Files modified:** tests/core/agent/tools/test_make_chart.py
- **Verification:** `python -m unittest tests.core.agent.tools.test_make_chart -v` exits 0 with 8/8 tests passing.
- **Committed in:** 015884e (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Isolated to test harness — tool module untouched. Conforms to cross-plan test-construction convention established by 02-03 and 02-04.

## Issues Encountered
None — plotly.express API behaved exactly as RESEARCH.md documented; `px.imshow(df)` on a 2x2 DataFrame returns `plotly.graph_objects.Figure` as expected.

## User Setup Required
None — no external service configuration required. Plotly is already pinned in `requirements.txt`.

## Next Phase Readiness
- **Wave 1 complete**: All 6 tools (run_sql, get_schema, pivot_to_wide, normalize_result, get_schema_docs, make_chart) are implemented and unit-tested. 6/6 tool modules exist under `app/core/agent/tools/`.
- **Ready for Plan 02-07** (Wave 2): TOOL_REGISTRY wiring in `app/core/agent/tools/__init__.py` can now import `make_chart_tool` alongside the other five and assert `len(TOOL_REGISTRY) == 6`.
- **Ready for Phase 3** (agent loop): `make_chart_tool(ctx, MakeChartArgs(...))` returns `ToolResult(chart=Figure)` — Phase 3 feeds `result.chart` to Streamlit via `st.plotly_chart(result.chart, use_container_width=True)` in Phase 4.

## Self-Check: PASSED

Verified claims:
- `app/core/agent/tools/make_chart.py`: FOUND
- `tests/core/agent/tools/test_make_chart.py`: FOUND
- Commit `00ce153` (Task 1): FOUND in `git log`
- Commit `015884e` (Task 2): FOUND in `git log`
- `python -m unittest tests.core.agent.tools.test_make_chart -v`: exit 0, 8 tests OK
- `isinstance(make_chart_tool, Tool)`: True
- Full test suite: 87/87 pass (no regressions)

---
*Phase: 02-tool-implementations*
*Plan: 06*
*Completed: 2026-04-23*
