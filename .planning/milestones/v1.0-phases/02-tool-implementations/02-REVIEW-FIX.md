---
phase: 02-tool-implementations
fixed_at: 2026-04-22T21:01:27Z
review_path: .planning/phases/02-tool-implementations/02-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 02: Code Review Fix Report

**Fixed at:** 2026-04-22T21:01:27Z
**Source review:** `.planning/phases/02-tool-implementations/02-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (3 Critical + 4 Warning; Info findings are out of scope)
- Fixed: 7
- Skipped: 0
- Full suite after all fixes: **107 tests pass, 0 failures** (`python -m unittest discover tests`)

## Fixed Issues

### CR-01: CTE body bypass — non-allowlisted tables inside `WITH ... AS (...)` are not extracted

**Files modified:** `app/core/agent/tools/_allowlist.py`, `tests/core/agent/tools/test_run_sql.py`
**Commit:** `a917f23` (combined with CR-02 — single walker code change closes both bypasses)
**Applied fix:** Rewrote `_extract_tables._recurse` so it unconditionally descends into every `is_group` token — including `Identifier` and `IdentifierList` groups — which the previous guard explicitly refused. Added a `recursed_as_target` flag to avoid double-walking a Parenthesis that was already recursed into as the target of a `FROM`/`JOIN`/`INTO` keyword. Result: a CTE body like `WITH leaked AS (SELECT * FROM secret_table)` now surfaces `secret_table` through the walker and the allowlist check rejects it, independent of the `_FORBIDDEN_SCHEMAS` substring net. Empirically verified: `_extract_tables("WITH leaked AS (SELECT * FROM secret_table) SELECT * FROM ufs_data")` now returns `{"ufs_data", "secret_table"}`. Added regression test `test_cte_body_rejection` using a non-forbidden-schema name.

### CR-02: Aliased-subquery bypass — `SELECT * FROM (SELECT * FROM secret_table) ufs_data` is accepted

**Files modified:** `app/core/agent/tools/_allowlist.py`, `tests/core/agent/tools/test_run_sql.py`
**Commit:** `a917f23` (combined with CR-01 — same walker change closes both)
**Applied fix:** Same walker change as CR-01. The Identifier group for `(SELECT * FROM secret_table) ufs_data` now has the walker descend into its Parenthesis child, surfacing `secret_table` in the extracted set. The allowlist check then rejects it even though the outer alias matches the allowlist. Empirically verified. Added regression test `test_aliased_subquery_rejection`.

### CR-03: Unhandled `AttributeError` from `IdentifierList.get_identifiers()` when a `Token` is returned

**Files modified:** `app/core/agent/tools/_allowlist.py`, `app/core/agent/tools/run_sql.py`, `tests/core/agent/tools/test_run_sql.py`
**Commit:** `cea8b17`
**Applied fix:** Two layers.
  1. In `_record`, added a defensive `hasattr(ident, "get_real_name")` + `hasattr(ident, "get_parent_name")` guard so bare `Token` instances yielded by `IdentifierList.get_identifiers()` (e.g. for MySQL `LATERAL` joins) are silently skipped instead of crashing with `AttributeError`. They are not table identifiers.
  2. In `run_sql.py`, wrapped `_check_table_allowlist` with `except Exception` (in addition to `except AllowlistError`) as belt-and-suspenders: any future sqlparse edge-case failure maps to a clean `SQL rejected: could not verify table allowlist.` ToolResult and is logged — never crashes the agent loop.

  Empirically verified: `_extract_tables("SELECT a.* FROM ufs_data a, LATERAL (SELECT * FROM secret_table) b")` no longer raises; the walker returns `{"ufs_data", "secret_table"}` and the allowlist rejects. Added regression test `test_no_attribute_error_on_exotic_sql`.

### WR-01: `_FORBIDDEN_SCHEMAS` substring check produces false positives on legitimate queries

**Files modified:** `app/core/agent/tools/_allowlist.py`, `tests/core/agent/tools/test_run_sql.py`
**Commit:** `e4991a5`
**Applied fix:** Chose Option (b) from REVIEW.md — tightened the belt-and-suspenders check to a word-boundary + dot-suffix regex `\b(information_schema|mysql|performance_schema|sys)\s*\.` (case-insensitive). This matches only actual schema prefixes (`mysql.user`, `information_schema.TABLES`) and no longer rejects legitimate UFS-domain content like `'mysql_buffer_size'`, `'system_busy_timeout'`, or comments `/* see information_schema tables */` (no dot after the word). Comment added explaining the AST walker is the authoritative check; the regex is defense-in-depth only. Empirically validated against all false-positive cases from the REVIEW.md. Added 4 regression tests covering the three false-positive cases plus a safety-net test ensuring `mysql.user` still rejects.

### WR-02: `normalize_result` compound-split silently drops rows whose value contains commas

**Files modified:** `app/core/agent/tools/normalize_result.py`, `tests/core/agent/tools/test_normalize_result.py`
**Commit:** `131dd2e`
**Applied fix:** Replaced `_COMPOUND_RE` regex with a stricter `_is_compound(s)` helper that requires **every** comma-separated segment to contain `=`. So `"x=foo,bar,y=baz"` no longer splits (the middle `bar` has no `=`), preserving the opaque string verbatim. Also added defensive per-pair `"=" in pair` and `k` non-empty guards inside `_split_compound_rows` so any future loosening can't corrupt the parameter-suffix column. Minimum-2-segments requirement so a single literal `k=v` (no comma) keeps its form. Added regression test `test_non_compound_value_with_embedded_comma_preserved` asserting one row in, one row out, value preserved byte-for-byte.

### WR-03: `pivot_to_wide` bypasses both safety gates (no `validate_and_sanitize`, no `_check_table_allowlist`)

**Files modified:** `app/core/agent/tools/pivot_to_wide.py`, `tests/core/agent/tools/test_pivot_to_wide.py`
**Commit:** `723ce48`
**Applied fix:** Routed pivot_to_wide's generated SELECT through both gates in the same order as `run_sql`: `validate_and_sanitize(sql, default_limit=ctx.config.row_cap)` first, then `_check_table_allowlist(sanitized, ctx.config.allowed_tables)`. On gate-1 failure, returns `SQL rejected: {reason}`; on gate-2 failure, returns `SQL rejected: {exc}`. Execution uses the sanitized SQL, not the raw one. Added two regression tests: `test_safety_gates_invoked` (wraps both gates with `patch(wraps=...)` to assert both are called exactly once during a happy-path pivot) and `test_empty_allowlist_fallback_is_rejected` (proves the hard-coded `ufs_data` fallback is caught when `allowed_tables=[]`, with no DB call made — covers the fallback-drift concern flagged in the review).

### WR-04: `get_schema` and `pivot_to_wide` are not covered by `log_query` — OBS-01 gap

**Files modified:** `app/core/agent/tools/get_schema.py`, `app/core/agent/tools/pivot_to_wide.py`, `tests/core/agent/tools/test_get_schema.py`, `tests/core/agent/tools/test_pivot_to_wide.py`
**Commit:** `e3da04f`
**Applied fix:**
  - **get_schema:** Added exactly one `log_query(...)` call per invocation, wrapping the full round-trip (schema lookup + two DISTINCT queries). Captures aggregate duration, combined row count (sum of distinct PLATFORM_ID + InfoCatergory values), and a collated `error` string if any internal call failed. User field tagged `"{user} [via get_schema]"` so the audit log can be filtered by source tool.
  - **pivot_to_wide:** Added `log_query(...)` calls at all four exit paths (success, safety-gate-1 rejection, safety-gate-2 rejection, DB exception) — exactly one per invocation. Success path logs the sanitized SQL, row count, and duration; rejection paths log the reason as `error`. DB-exception path masks the user-facing message (`"Query failed: database error..."`) but preserves full error in the log.

  Added regression tests `test_single_log_per_invocation` (get_schema), `test_single_log_on_success`, and `test_single_log_on_empty_allowlist_rejection` (both pivot_to_wide) asserting `mock_log.call_count == 1` and verifying the `[via ...]` user prefix. Existing tests for `get_schema` continue to pass unchanged because they don't exercise the log path; the new log integration is additive.

## Skipped Issues

None — all 7 in-scope findings were fixed cleanly.

## Verification Run

After all 7 fixes, the full suite was re-run:

```
python -m unittest discover tests
Ran 107 tests in 2.388s
OK
```

Affected test suites (per-fix verification):
- `tests.core.agent.tools.test_run_sql`: 20 tests (was 13 — added 7: CR-01, CR-02, CR-03 + 4 WR-01)
- `tests.core.agent.tools.test_pivot_to_wide`: 12 tests (was 8 — added 4: 2 WR-03, 2 WR-04)
- `tests.core.agent.tools.test_normalize_result`: 13 tests (was 12 — added 1: WR-02)
- `tests.core.agent.tools.test_get_schema`: 6 tests (was 5 — added 1: WR-04)
- **Total delta: +13 regression tests, 0 removed, 0 modified.**

No pre-existing tests required updates.

## Commit Log (atomic, in order)

| # | Hash | Finding(s) | Files |
|---|------|-----------|-------|
| 1 | `a917f23` | CR-01 + CR-02 | `_allowlist.py`, `test_run_sql.py` |
| 2 | `cea8b17` | CR-03 | `_allowlist.py`, `run_sql.py`, `test_run_sql.py` |
| 3 | `e4991a5` | WR-01 | `_allowlist.py`, `test_run_sql.py` |
| 4 | `131dd2e` | WR-02 | `normalize_result.py`, `test_normalize_result.py` |
| 5 | `723ce48` | WR-03 | `pivot_to_wide.py`, `test_pivot_to_wide.py` |
| 6 | `e3da04f` | WR-04 | `get_schema.py`, `pivot_to_wide.py`, `test_get_schema.py`, `test_pivot_to_wide.py` |

CR-01 and CR-02 share the same walker code fix (unconditional recursion into every group), so a single atomic commit closes both bypasses with both regression tests. All five other findings have their own distinct commits.

---

_Fixed: 2026-04-22T21:01:27Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
