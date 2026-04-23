---
phase: 02-tool-implementations
plan: 04
subsystem: agent-tools
tags: [normalize_result, clean_result, pandas, dataframe-cache, pydantic, hex-parsing, compound-split, ufs, tool-07]

# Dependency graph
requires:
  - phase: 01-agent-scaffold
    provides: "AgentContext._df_cache with store_df/get_df; Tool Protocol; ToolResult model"
  - phase: 02-tool-implementations
    provides: "AgentContext.current_tool_call_id (added by plan 02-03) enabling deterministic cache keys; pivot_to_wide_tool as upstream df_ref producer"
provides:
  - "normalize_result_tool — TOOL-04 UFS spec §5 clean_result applied to cached DataFrames"
  - "NormalizeResultArgs (Pydantic BaseModel) exposing data_ref via model_json_schema for TOOL-07"
  - "_clean_cell helper: hex→int (int(s,16)), int/float parsing, null-likes ('None','nan','','-','n/a')→pd.NA, pass-through"
  - "_split_compound_rows helper: row-split of 'local=1,peer=2' with parameter/Item column suffix (_local/_peer) per RESEARCH.md Open Question #1 resolution"
  - "Deterministic derived cache key format f'{data_ref}:normalized' — human-readable in logs"
  - "Missing-ref friendly error path (no crash, no cache write, df_ref=None)"
affects: [02-06-make_chart, 02-07-registry, 03-agent-loop, 05-domain-review]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tool-local helpers (_clean_cell, _split_compound_rows) remain in the tool module since no other Phase 2 tool needs them (CONTEXT.md §decisions)"
    - "Elementwise DataFrame transformation via df.map (NOT deprecated .applymap — Pitfall 1 guard)"
    - "Deterministic derived cache key (f'{src}:normalized') preferred over uuid for traceability in logs"
    - "Long-form vs wide-form dispatch by column sentinel ('Result' column triggers row-split; otherwise elementwise map)"

key-files:
  created:
    - app/core/agent/tools/normalize_result.py
    - tests/core/agent/tools/test_normalize_result.py
  modified: []

key-decisions:
  - "Row-split interpretation (not column-split) for compound 'local=1,peer=2' values — RESEARCH.md Open Question #1 resolution / Assumption A1; flagged for Phase 5 domain review"
  - "_clean_cell / _split_compound_rows stay in normalize_result.py (tool-local) rather than a shared _normalize.py — no other Phase 2 tool consumes these helpers"
  - "Deterministic derived cache key f'{data_ref}:normalized' instead of uuid — preserves traceability in queries.log and enables predictable downstream df_ref references"
  - "Missing data_ref returns ToolResult(content='No DataFrame cached at ...', df_ref=None) — model can recover within step budget instead of the turn crashing"
  - "Use df.map (pandas 3.0-safe) for wide-form elementwise mapping; .applymap explicitly avoided per Pitfall 1"
  - "_clean_cell null-check ordering: pd.NA / None / float-NaN shortcut BEFORE str() conversion to avoid 'NA'/'nan' string collisions on pd.NA input"

patterns-established:
  - "Tool-local regex constants at module scope (_HEX_RE, _INT_RE, _FLOAT_RE, _NULL_LIKE, _COMPOUND_RE) — pre-compiled once per process"
  - "Row-split helper returns a fresh DataFrame via list-of-dicts + reset_index(drop=True) — keeps compound expansions type-consistent and index-clean"
  - "Long-form/wide-form sentinel: presence of 'Result' column decides the normalization strategy — keeps the tool single-entry while covering both shapes"

requirements-completed: [TOOL-04, TOOL-07]

# Metrics
duration: ~8 min
completed: 2026-04-23
---

# Phase 2 Plan 4: normalize_result Tool Summary

**TOOL-04 normalize_result applies UFS spec §5 cleanup (hex→int, numeric parse, null-likes→pd.NA, compound 'local=1,peer=2' row-split with parameter suffix) to a cached DataFrame and writes the cleaned result back under a deterministic `f'{data_ref}:normalized'` key, returning df_ref for downstream make_chart consumption.**

## Performance

- **Duration:** ~8 min
- **Tasks:** 2 (both completed sequentially on main working tree)
- **Files created:** 2 (1 tool module, 1 test module)
- **Test count delta:** +13 tests (across 8 TestCases); whole agent dir now 65 tests, all green

## Accomplishments

- `normalize_result_tool` implements TOOL-04 end-to-end: reads `ctx.get_df(data_ref)`, dispatches long-form (has `Result` column) to `_split_compound_rows` vs wide-form to `df.map(_clean_cell)`, writes cleaned DF to `ctx.store_df(f'{data_ref}:normalized', ...)`, returns ToolResult with df_ref.
- `_clean_cell` handles every UFS §5 transformation verified in RESEARCH.md (hex, signed int, signed float, eight null-likes, pass-through, pd.NA/None/NaN inputs).
- `_split_compound_rows` implements the row-split interpretation (Assumption A1 / RESEARCH.md Open Question #1) with a graceful degrade path when neither `parameter` nor `Item` column is available.
- 13 tests across 8 TestCase classes cover clean_cell transformations, Pydantic arg validation, TEST-01 compound domain edge, long-form hex parsing, wide-form elementwise mapping, missing-ref safety, derived-ref format, and Tool Protocol compliance.
- SAFE-07 compliant across all new files: no correctly-spelled `InfoCategory` anywhere in this plan's surface.
- Pitfall 1 guard verified: zero `.applymap(` usages; elementwise mapping uses pandas-3.0-safe `df.map`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create normalize_result.py (tool module)** — `446bdbd` (feat)
2. **Task 2: Create test_normalize_result.py (unit tests)** — `a88282e` (test)

## Files Created/Modified

- `app/core/agent/tools/normalize_result.py` — New: `NormalizeResultArgs` (Pydantic), `NormalizeResultTool` class satisfying Tool Protocol, module-level `normalize_result_tool` singleton, tool-local helpers `_clean_cell` / `_split_compound_rows` / regex constants.
- `tests/core/agent/tools/test_normalize_result.py` — New: 8 unittest TestCases covering clean_cell transformations (hex, int, float, null-likes, pass-through, pd.NA), Pydantic missing-arg validation, TEST-01 compound row-split domain edge, long-form hex parsing, wide-form elementwise mapping, missing-ref safety, derived-ref format, and Tool Protocol compliance.

## Decisions Made

- **Row-split interpretation of compound values** (`wb_enable` with `Result="local=1,peer=2"` → two rows with `parameter` suffixed `_local` / `_peer`) per RESEARCH.md Open Question #1 resolution and Assumption A1. This keeps the downstream wide pivot 1:1 with parameter keys and avoids ambiguous column proliferation. **Phase 5 domain review must validate this against real seed data** — if the domain expert expects column-split, a minor refactor inside `_split_compound_rows` (replace per-row emission with a pivot on the compound key) switches the interpretation without changing the tool's public contract.
- **Tool-local helper placement** — `_clean_cell` and `_split_compound_rows` live inside `normalize_result.py` rather than `_normalize.py` because no other Phase 2 tool consumes them (CONTEXT.md §decisions: "Prefer former [tool-local] unless another tool needs the same helper").
- **Deterministic derived cache key `f'{data_ref}:normalized'`** — preferred over `uuid4()` per RESEARCH.md for human-readable traceability in logs and predictable df_ref references for downstream `make_chart`.
- **Null-check ordering** — `pd.NA` / `None` / float-NaN sentinel checked BEFORE `str()` conversion to avoid edge cases where `str(pd.NA) == 'NA'` would collide with the null-like set (which intentionally excludes bare `"NA"` to let genuine parameter identifiers pass through).
- **Long-form vs wide-form dispatch by column sentinel** — presence of `Result` column triggers row-split; absence triggers elementwise `df.map`. Keeps the tool single-entry and covers both shapes pivot_to_wide can produce upstream.
- **Pandas-3.0-safe `df.map`** explicitly used (not `.applymap`) per Pitfall 1; enforced by grep in acceptance criteria.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0
**Impact on plan:** Clean execution — both tasks performed verbatim per PLAN.md `<action>` blocks; all acceptance-criteria greps returned exact expected counts; all 13 tests passed on first run with no adjustments needed.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Phase 5 Flag: Row-Split Assumption (A1)

The interpretation that `"local=1,peer=2"` splits into TWO rows with `parameter`/`Item` suffixed `_local` / `_peer` is an **assumption** pending domain expert verification. If Phase 5 seed data shows that UFS analysts expect the compound split to produce **columns** (e.g., `Result_local`, `Result_peer`) instead of rows, the fix is localized to `_split_compound_rows` in `app/core/agent/tools/normalize_result.py`:

- Current behavior: per-row compound pair emission via list-of-dicts, parameter column gets `_<key>` suffix.
- Alternative: pivot on compound keys within the Result column, emit new columns `Result_local` / `Result_peer`, leave row count unchanged.

The tool's public contract (`NormalizeResultArgs(data_ref)` → `ToolResult(df_ref=...)`) and cache-key format (`f'{data_ref}:normalized'`) remain unchanged under either interpretation — only the internal helper shape changes. No upstream or downstream tool code would need modification.

## Next Phase Readiness

- `normalize_result_tool` is exported from `app.core.agent.tools.normalize_result` and ready for plan 02-07's `TOOL_REGISTRY` import.
- Plan 02-06 (`make_chart`) can read the normalized DF via `ctx.get_df(f'{upstream_ref}:normalized')` — the derived key format is deterministic and stable.
- Phase 3's agent loop can surface `ctx.current_tool_call_id` as `data_ref` input (normalize follows pivot_to_wide's cache key), or the model can pass the prior tool's returned df_ref explicitly via args — both paths are supported.
- Phase 5 domain review checkpoint: validate row-split vs column-split interpretation against real seed data.

## Self-Check: PASSED

- `app/core/agent/tools/normalize_result.py` exists (106 lines)
- `tests/core/agent/tools/test_normalize_result.py` exists (142 lines, 13 tests passing)
- Commits `446bdbd`, `a88282e` present in `git log`
- `python -m unittest tests.core.agent.tools.test_normalize_result -v` → Ran 13 tests, OK
- `python -m unittest discover -s tests/core/agent` → Ran 65 tests, OK (no Phase 1/2 regressions — includes 13 new from this plan)
- `grep -rE 'InfoCategory\b' app/core/agent/tools/normalize_result.py tests/core/agent/tools/test_normalize_result.py` → 0 matches (SAFE-07 clean)
- `grep -c 'applymap' app/core/agent/tools/normalize_result.py` → 0 (Pitfall 1 guard)
- `isinstance(normalize_result_tool, Tool)` → True (Protocol compliance verified at runtime)

---
*Phase: 02-tool-implementations*
*Plan: 04*
*Completed: 2026-04-23*
