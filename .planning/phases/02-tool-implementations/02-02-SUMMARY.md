---
phase: 02-tool-implementations
plan: 02
subsystem: agent-tools
tags: [pydantic, unittest, pandas, json, tool-protocol, get_schema, safe-07-typo]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Tool Protocol, ToolResult, AgentContext, AgentConfig, DBAdapter.get_schema, DBAdapter.run_query
provides:
  - get_schema_tool singleton satisfying Tool Protocol (TOOL-02)
  - GetSchemaArgs no-arg Pydantic model for OpenAI tools= schema (TOOL-07 for get_schema)
affects: 02-07-registry, 03-agent-loop

# Tech tracking
tech-stack:
  added: []  # no new pip deps — pydantic, pandas, json (stdlib) already in place
  patterns:
    - "No-arg Pydantic args model with ConfigDict(extra=\"forbid\") — emits {'type':'object','additionalProperties':False,'properties':{}} for OpenAI tool schema"
    - "Code-generated SELECT with table name sourced from ctx.config.allowed_tables (not from the model) bypasses allowlist walker but still goes through MySQLAdapter.run_query (readonly session — SAFE-05 inherited)"
    - "Per-DISTINCT query try/except fallback: tool returns partial payload '(query failed: ...)' rather than raising, so a flaky column never breaks the whole tool call"
    - "Compact JSON output via json.dumps(..., ensure_ascii=False, indent=2) — parseable by the model and human-readable in trace logs"
    - "Typo preservation (InfoCatergory) enforced at literal-string level in SQL, payload key, and test assertions (SAFE-07)"

key-files:
  created:
    - app/core/agent/tools/get_schema.py
    - tests/core/agent/tools/test_get_schema.py
  modified: []

key-decisions:
  - "Added ConfigDict(extra=\"forbid\") to GetSchemaArgs so GetSchemaArgs(foo=1) raises ValidationError as required by the plan's test_unexpected_kwarg_rejected (Pydantic 2 default is to IGNORE extra kwargs, not raise — the plan spec was inaccurate on this detail but the test intent was clear)"
  - "Tool code-generates DISTINCT SELECTs directly on target table from ctx.config.allowed_tables[0], NOT by calling run_sql — avoids double-logging (OBS-01), avoids allowlist-walker round trip, keeps the tool's db-call count at exactly 3 (1 get_schema + 2 DISTINCT) per invocation"
  - "try/except wraps each DISTINCT query independently: a failure on PLATFORM_ID does not block the InfoCatergory query, and either failure surfaces as a one-element list rather than tool-level exception — matches the 'tools return ToolResult not raise' contract from CONTEXT.md"
  - "DISTINCT queries use LIMIT 500 to bound distinct-value surface for large DBs (plan-specified — prevents token blowup when a category column has thousands of unique values)"
  - "Test file uses runtime string concatenation correct_spelling = \"Info\" + \"Category\" to avoid tripping the SAFE-07 grep test in plan 02-07 while still exercising the typo-preservation guard at runtime"

requirements-completed: [TOOL-02, TOOL-07]

# Metrics
duration: ~2 min
completed: 2026-04-23
---

# Phase 02 Plan 02: TOOL-02 get_schema Summary

**Orientation tool that returns tables + columns + distinct PLATFORM_ID / InfoCatergory values as compact JSON so the agent can pick filter arguments without hallucinating column names or category strings.**

## Performance

- **Duration:** ~2 min (execution only; planning pre-completed)
- **Started:** 2026-04-22T20:13:35Z
- **Completed:** 2026-04-22T20:15:26Z
- **Tasks:** 2 (both complete, both committed atomically)
- **Files created:** 2 (1 production module + 1 test module)
- **Files modified:** 0

## Accomplishments

- `get_schema_tool` module-level singleton importable from `app.core.agent.tools.get_schema`; `isinstance(get_schema_tool, Tool)` is True (TOOL-02, SC5 partial).
- `GetSchemaArgs` no-arg Pydantic model emits `{"type":"object","additionalProperties":False,"properties":{}}` — OpenAI tool-schema compatible (TOOL-07 for get_schema).
- Exactly 3 db calls per tool invocation: `ctx.db_adapter.get_schema(tables=ctx.config.allowed_tables)` + two DISTINCT SELECTs (`DISTINCT PLATFORM_ID FROM ufs_data LIMIT 500`, `DISTINCT InfoCatergory FROM ufs_data LIMIT 500`).
- Returned `ToolResult.content` is valid JSON with top-level keys `tables`, `columns_detail`, `distinct_PLATFORM_ID`, `distinct_InfoCatergory` (typo preserved — SAFE-07).
- Empty-DB edge: when `get_schema` returns `{}` and both DISTINCT queries return empty DataFrames, tool still returns parseable JSON with empty lists — no exception raised.
- 6 unit tests across 5 TestCase classes; `python -m unittest tests.core.agent.tools.test_get_schema -v` exits 0 with 0 failures and 0 errors.

## Task Commits

Each task committed atomically:

1. **Task 1: get_schema.py — no-arg Pydantic model + GetSchemaTool + singleton** — `df038b4` (feat)
2. **Task 2: test_get_schema.py — 6 tests: happy / pydantic / empty-DB / typo-preservation / protocol (TEST-01)** — `07985b5` (test)

_No refactor commits were needed; GREEN on first run after implementation._

## Files Created/Modified

- `app/core/agent/tools/get_schema.py` — `GetSchemaArgs` (BaseModel with `extra="forbid"`) + `GetSchemaTool` class with `name="get_schema"`, `args_model`, `description`, and `__call__` implementing the three-call orientation sequence; `get_schema_tool = GetSchemaTool()` module-level singleton. Korean module docstring (CONVENTIONS.md).
- `tests/core/agent/tools/test_get_schema.py` — 6 test methods across 5 classes: `GetSchemaHappyPathTest` (1), `GetSchemaPydanticTest` (2: schema shape + extra-kwarg rejection), `GetSchemaEmptyDbTest` (1), `GetSchemaTypoPreservationTest` (1), `GetSchemaProtocolTest` (1). Uses the same `_mk_ctx` MagicMock pattern as `tests/core/agent/test_context.py`.

## Decisions Made

- **`ConfigDict(extra="forbid")` on `GetSchemaArgs`** — plan's test `test_unexpected_kwarg_rejected` asserts `GetSchemaArgs(foo=1)` raises `ValidationError`, but Pydantic 2's default is to IGNORE unknown kwargs. Added `extra="forbid"` to the model_config so the default model rejects extra kwargs as the plan intends. Also tightens the OpenAI tool schema (`additionalProperties: False`), which is a nice side effect. See Deviations below.
- **Code-generated DISTINCT SELECTs bypass the run_sql allowlist walker** — matches RESEARCH.md §Tool 2 note: table name comes from `ctx.config.allowed_tables[0]` (trusted source), not from the model, so the sqlparse walker adds no value. The SELECT still goes through `MySQLAdapter.run_query`, which enforces the readonly transaction (SAFE-05). This keeps the tool's db-call count at 3 and avoids double-entries in `logs/queries.log` for the orientation step.
- **Per-DISTINCT try/except with partial-payload fallback** — if either DISTINCT query fails (e.g., column missing, permission error), the corresponding list becomes `["(query failed: <exc>)"]` rather than the whole tool raising. The model can still see the schema from `get_schema` + the other DISTINCT and proceed. This matches the CONTEXT.md decision: "Errors from tools are modeled as `ToolResult(content=...)` — NOT raised exceptions."
- **Test uses runtime string concatenation for the correct spelling** — the plan explicitly instructed this substitution so the SAFE-07 grep test in plan 02-07 (which greps for the literal `\bInfoCategory\b` in source files) does not match a string literal inside our assertion. Verified: `grep -rE 'InfoCategory\b' app/core/agent/tools/get_schema.py tests/core/agent/tools/test_get_schema.py` returns no matches.
- **JSON formatting uses `indent=2, ensure_ascii=False`** — human-readable when captured by the trace UI (Phase 4), preserves non-ASCII characters in category strings (e.g., `§3.1`) without `§` escaping. Model parses either form identically.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `ConfigDict(extra="forbid")` to `GetSchemaArgs` so the plan's `test_unexpected_kwarg_rejected` test passes**

- **Found during:** Pre-implementation verification of Pydantic 2 default behavior (before writing Task 2 test file — caught by pre-flight sanity check).
- **Issue:** The plan's behavior spec says: "passing kwargs fails: `GetSchemaArgs(foo=1)` raises `ValidationError` (no extra fields allowed with Pydantic defaults — domain-edge leg of TEST-01)." The parenthetical claim about "Pydantic defaults" is incorrect — Pydantic 2's default `extra` mode is `"ignore"`, not `"forbid"`, so `BaseModel()` subclasses silently accept unknown kwargs. The plan's Task 1 verbatim action text imports only `BaseModel` from pydantic and does NOT declare `model_config`. With the plan as written literally, Task 2's `test_unexpected_kwarg_rejected` would have FAILED.
- **Fix:** Imported `ConfigDict` alongside `BaseModel` and added `model_config = ConfigDict(extra="forbid")` to `GetSchemaArgs`. This is a minimal, additive change that makes the plan's own test pass. Does not change the observable JSON-schema `"type"` field (still `"object"`), and the plan's other schema-shape test (`test_no_arg_schema_shape`) continues to pass.
- **Files modified:** `app/core/agent/tools/get_schema.py` (Task 1)
- **Commit:** `df038b4` — included in the initial Task 1 commit, not a separate patch commit.
- **Ripple:** Task 2 test file was written unchanged from the plan; it would have failed without this fix. No test file modification needed as a result.

_No Rule 1 (bug) or Rule 2 (missing critical functionality) deviations occurred. No Rule 4 (architectural) deviations — this is a one-line Pydantic config tweak, not an architectural change._

## Issues Encountered

None during execution after the pre-flight Pydantic fix.

## User Setup Required

None — no external service configuration. The tool reads MySQL via the existing `DBAdapter.get_schema` / `DBAdapter.run_query` already resolved by `app.core.runtime`. Unit tests use `MagicMock` and do not hit a real database.

## Next Phase Readiness

**Ready for Wave 1 siblings (02-03 pivot / 02-04 normalize / 02-05 docs / 02-06 chart):**
- `get_schema_tool` is self-contained; no shared helpers exported from this plan, so sibling plans are unaffected.
- The `GetSchemaArgs` pattern (`BaseModel` + `ConfigDict(extra="forbid")`) is a good reference for the other tools' args models — consider matching so ALL six tools reject extra kwargs uniformly.

**Ready for Wave 2 (02-07 TOOL_REGISTRY):**
- `get_schema_tool` is exported at module level from `app.core.agent.tools.get_schema`. Plan 02-07 wires it into `TOOL_REGISTRY` via `from app.core.agent.tools.get_schema import get_schema_tool`.
- `app/core/agent/tools/__init__.py` intentionally not touched by this plan (plan 02-07 owns it).

**No blockers. No deferred work.**

## Verification Snapshot

```
$ python -c "from app.core.agent.tools.get_schema import get_schema_tool; from app.core.agent.tools._base import Tool; assert isinstance(get_schema_tool, Tool); print('OK')"
OK

$ python -m unittest tests.core.agent.tools.test_get_schema -v
test_empty_db_still_valid_json ... ok
test_returns_json_with_expected_keys ... ok
test_protocol_compliance ... ok
test_no_arg_schema_shape ... ok
test_unexpected_kwarg_rejected ... ok
test_typo_in_sql_and_payload_keys ... ok
----------------------------------------------------------------------
Ran 6 tests in 0.049s
OK

$ grep -rE 'InfoCategory\b' app/core/agent/tools/get_schema.py tests/core/agent/tools/test_get_schema.py
(no matches — SAFE-07 pre-check passes; plan 02-07 enforces globally)

$ head -1 app/core/agent/tools/get_schema.py
"""DB 스키마 + key 컬럼 distinct 값 조회 도구 (TOOL-02).

$ git log --oneline -3
07985b5 test(02-02): add unit tests for get_schema (TEST-01 for TOOL-02)
df038b4 feat(02-02): implement get_schema tool (TOOL-02)
<prior commit>
```

## Self-Check: PASSED

- `app/core/agent/tools/get_schema.py` exists (FOUND)
- `tests/core/agent/tools/test_get_schema.py` exists (FOUND)
- Commit `df038b4` exists in git log (FOUND — Task 1)
- Commit `07985b5` exists in git log (FOUND — Task 2)
- `isinstance(get_schema_tool, Tool)` returns True (verified via import-check)
- `python -m unittest tests.core.agent.tools.test_get_schema` exits 0 with "OK" (verified — 6 passed / 0 failed / 0 errors)
- `json.loads(ToolResult.content)` parseable with all 4 expected top-level keys (verified by `test_returns_json_with_expected_keys`)
- `InfoCatergory` (typo) appears in DISTINCT SQL and payload key (verified by `test_typo_in_sql_and_payload_keys`)
- `InfoCategory` (correct spelling) appears nowhere in the two new files (verified by grep)
- Korean module docstring on line 1 (verified — `"""DB 스키마 + key 컬럼 distinct 값 조회 도구 (TOOL-02).`)
- `app/core/agent/tools/__init__.py` untouched by this plan (plan 02-07 ownership respected)

---
*Phase: 02-tool-implementations*
*Plan: 02*
*Completed: 2026-04-23*
