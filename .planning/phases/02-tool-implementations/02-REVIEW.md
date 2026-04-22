---
phase: 02-tool-implementations
reviewed: 2026-04-23T00:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - app/core/agent/context.py
  - app/core/agent/tools/__init__.py
  - app/core/agent/tools/_allowlist.py
  - app/core/agent/tools/get_schema.py
  - app/core/agent/tools/get_schema_docs.py
  - app/core/agent/tools/make_chart.py
  - app/core/agent/tools/normalize_result.py
  - app/core/agent/tools/pivot_to_wide.py
  - app/core/agent/tools/run_sql.py
  - app/core/agent/tools/spec/section_1.txt
  - app/core/agent/tools/spec/section_2.txt
  - app/core/agent/tools/spec/section_3.txt
  - app/core/agent/tools/spec/section_4.txt
  - app/core/agent/tools/spec/section_5.txt
  - app/core/agent/tools/spec/section_6.txt
  - app/core/agent/tools/spec/section_7.txt
  - tests/core/agent/test_context_tool_call_id.py
  - tests/core/agent/tools/test_get_schema.py
  - tests/core/agent/tools/test_get_schema_docs.py
  - tests/core/agent/tools/test_make_chart.py
  - tests/core/agent/tools/test_no_correct_spelling.py
  - tests/core/agent/tools/test_normalize_result.py
  - tests/core/agent/tools/test_pivot_to_wide.py
  - tests/core/agent/tools/test_registry.py
  - tests/core/agent/tools/test_run_sql.py
findings:
  critical: 3
  warning: 4
  info: 5
  total: 12
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-04-23
**Depth:** standard
**Files Reviewed:** 18 (9 source + 7 spec + tests)
**Status:** issues_found

## Summary

Phase 2 ships six agent tools, the allowlist walker, and comprehensive unit tests. Overall test quality is high — rejection-path tests correctly assert `db_adapter.run_query.assert_not_called()`, the framing sentence is byte-exact asserted, and the SAFE-07 typo-preservation grep guard includes a meta-test that verifies the scanner works. Korean module docstrings are preserved on every module (eight modules checked via `head -1`). Double-logging (OBS-01) is correctly avoided: `get_schema` calls `db_adapter.run_query` directly and does not route through `log_query`. Pydantic 2 emission is correct (Literal → enum, ge/le → minimum/maximum).

However, empirical testing of the allowlist walker (`_check_table_allowlist`) surfaced **three allowlist bypass paths** that defeat SAFE-01. Two are logic errors in `_extract_tables`, and one is an unhandled exception. These are non-negotiable per the plan and must be fixed before Phase 3 integration. A handful of lower-severity issues (substring false-positives, compound-split data loss, private-attribute access, missing `description` on two tools) round out the report.

## Critical Issues

### CR-01: CTE body bypass — non-allowlisted tables inside `WITH ... AS (...)` are not extracted

**File:** `app/core/agent/tools/_allowlist.py:40-63`
**Issue:** `_extract_tables("WITH leaked AS (SELECT * FROM secret_table) SELECT * FROM ufs_data")` returns `{'ufs_data'}`. `secret_table` inside the CTE body is never visited, so `_check_table_allowlist` accepts the query. Verified empirically:

```
>>> _extract_tables('WITH leaked AS (SELECT * FROM secret_table) SELECT * FROM ufs_data')
{'ufs_data'}
>>> _check_table_allowlist(...)
# passes — BYPASS
```

Root cause: `WITH` is not in `_TABLE_KEYWORDS`, so when the walker reaches the `Identifier` token `leaked AS (...)`, `prev_kw` is `None` and the Identifier is not recorded. Then the descent guard `if tok.is_group and not isinstance(tok, (Identifier, IdentifierList))` **explicitly refuses to descend into Identifiers**, so the Parenthesis inside is never walked. Any `SELECT * FROM non_allowed_table` inside a CTE body is silently permitted.

Note: the existing test `test_cte_subquery_to_information_schema_rejected` passes only because the `_FORBIDDEN_SCHEMAS` substring check rescues that one case (`information_schema` appears in the SQL text). Replace `information_schema.TABLES` with any other non-allowlisted name and the query will be accepted.

**Fix:** Unconditionally recurse into every group, and add `WITH` to `_TABLE_KEYWORDS`. Minimal patch:
```python
# _allowlist.py
_TABLE_KEYWORDS = {
    "FROM", "JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN",
    "FULL JOIN", "CROSS JOIN", "LEFT OUTER JOIN", "RIGHT OUTER JOIN",
    "UPDATE", "INTO",
}  # (WITH not strictly needed if we descend into every group)

def _recurse(tok_list) -> None:
    prev_kw: str | None = None
    for tok in tok_list.tokens:
        if tok.is_whitespace:
            continue
        # ... existing record logic ...
        # REPLACE the guarded descent with unconditional descent:
        if tok.is_group:
            _recurse(tok)
```
Add a regression test using a fabricated non-reserved table name (e.g. `secret_table`) inside a CTE body to prevent reliance on the forbidden-schema substring net.

---

### CR-02: Aliased-subquery bypass — `SELECT * FROM (SELECT * FROM secret_table) ufs_data` is accepted

**File:** `app/core/agent/tools/_allowlist.py:32-67`
**Issue:** When a subquery is aliased to match an allowlisted name, the walker records only the alias. Verified empirically:

```
>>> _extract_tables('SELECT * FROM (SELECT * FROM secret_table) ufs_data')
{'ufs_data'}
>>> _check_table_allowlist(sql, ['ufs_data'])
# passes — BYPASS
```

`sqlparse` builds an `Identifier` for `(SELECT * FROM secret_table) ufs_data` whose `get_real_name()` returns `ufs_data` (the alias). The walker records `ufs_data`, but never descends into the inner Parenthesis, so `secret_table` is never extracted. The user-facing impact is identical to CR-01: arbitrary non-allowlisted tables can be read through a subquery-with-alias.

**Fix:** Same patch as CR-01 — always recurse into groups, including Identifiers whose children may contain a Parenthesis. Add a direct regression test:
```python
def test_aliased_subquery_bypass_rejected(self):
    sql = "SELECT * FROM (SELECT * FROM secret_table) ufs_data"
    with self.assertRaises(AllowlistError):
        _check_table_allowlist(sql, ["ufs_data"])
```

---

### CR-03: Unhandled `AttributeError` from `IdentifierList.get_identifiers()` when a `Token` is returned

**File:** `app/core/agent/tools/_allowlist.py:32-38, 49-52`
**Issue:** For certain MySQL-specific syntax (LATERAL joins, some comma-joined edge cases), `sqlparse` yields a bare `Token` inside `IdentifierList.get_identifiers()` rather than an `Identifier`. `Token` has no `get_parent_name()` method, so `_record(ident)` raises `AttributeError: 'Token' object has no attribute 'get_parent_name'`. Verified:

```
>>> _extract_tables('SELECT a.* FROM ufs_data a, LATERAL (SELECT * FROM secret_table) b')
AttributeError: 'Token' object has no attribute 'get_parent_name'
```

`run_sql_tool.__call__` does not wrap `_check_table_allowlist` in a broad `except Exception` — only `except AllowlistError`. So this exception propagates up to the agent loop as an unhandled crash, not a clean `"SQL rejected: ..."` response.

**Fix:** Defensively guard `_record()`:
```python
def _record(ident) -> None:
    if not hasattr(ident, "get_real_name"):
        return  # bare Token — not a table identifier
    parent = ident.get_parent_name()
    real = ident.get_real_name()
    if real is None:
        return
    full = f"{parent}.{real}" if parent else real
    tables.add(full.lower())
```
Also consider wrapping `_check_table_allowlist` in `run_sql.py` with `except Exception` that maps to a rejected-SQL result, so future sqlparse edge cases can't crash the agent loop.

---

## Warnings

### WR-01: `_FORBIDDEN_SCHEMAS` substring check produces false positives on legitimate queries

**File:** `app/core/agent/tools/_allowlist.py:19, 72-76`
**Issue:** The substring belt-and-suspenders check uses naked `if forbidden in lowered`, which matches `sys` inside any word containing those three letters. Legitimate queries are rejected:

- `SELECT * FROM ufs_data WHERE parameter = 'mysql_buffer_size'` → rejected (`mysql` in string literal)
- `SELECT * FROM ufs_data WHERE description LIKE '%system performance%'` → rejected (`sys` in `system`)
- `SELECT * FROM ufs_data /* see information_schema.tables */` → rejected on comment

This is a high-noise guard. Once CR-01/CR-02 are fixed, the AST walker catches these properly. The substring net then provides diminishing value and blocks real-world UFS domain phrases (the `Item` column values include names like `system_busy_timeout`, etc.).

**Fix:** Either (a) remove `_FORBIDDEN_SCHEMAS` entirely and rely on the fixed AST walker, or (b) tighten to word-boundary + dot-suffix: `re.compile(rf"\b{re.escape(s)}\.", re.IGNORECASE)` — matches only when used as a schema prefix (`information_schema.tables`), not when appearing inside string literals. Option (b) keeps defense-in-depth.

---

### WR-02: `normalize_result` compound-split silently drops rows whose value contains commas

**File:** `app/core/agent/tools/normalize_result.py:23, 41-61`
**Issue:** `_COMPOUND_RE = r"^\s*\w+\s*=.+(,\s*\w+\s*=.+)+\s*$"` matches any string that begins with `word=anything` followed by one or more `,word=anything` segments. This means a value like `"x=foo,bar,y=baz"` is treated as compound and `split(",")` produces three segments. The middle segment `"bar"` has no `=`, so `partition("=")` returns `("bar", "", "")`. The code then creates a row with parameter suffix `_bar` (because `k="bar"`) and `Result=""`, which `_clean_cell` maps to `pd.NA` (empty string is in `_NULL_LIKE`). Real data is silently replaced by NA.

**Fix:** Require every comma-separated segment to contain `=` before treating the value as compound:
```python
def _is_compound(s: str) -> bool:
    if "," not in s or "=" not in s:
        return False
    return all("=" in part for part in s.split(","))
```
And inside `_split_compound_rows`, skip any pair missing `=`. Add a regression test for `x=foo,bar,y=baz`.

---

### WR-03: `pivot_to_wide` bypasses both safety gates (no `validate_and_sanitize`, no `_check_table_allowlist`)

**File:** `app/core/agent/tools/pivot_to_wide.py:46-56`
**Issue:** `pivot_to_wide` constructs SQL directly from `ctx.config.allowed_tables[0]` and user-provided filter strings, escapes single quotes, and calls `ctx.db_adapter.run_query(sql)`. It does not pass through `validate_and_sanitize` (no auto-LIMIT normalization of `ctx.config.row_cap`; LIMIT is hard-coded inline — OK in practice but not checked) and does not call `_check_table_allowlist`. The SQL shape is static and the table name comes from config, so the current exposure is limited, but:

- If `ctx.config.allowed_tables` is ever empty, the fallback `"ufs_data"` is hard-coded at line 48 — inconsistent with the single source of truth.
- The `_sql_escape` function handles only single quotes. It does not handle backslash (MySQL with `NO_BACKSLASH_ESCAPES` OFF can interpret `\'` as an escaped quote, breaking the doubling). If MySQL ever runs without that mode, `category="O'\\''Brien"` or similar could recombine.
- A future change that allows multiple tables in `allowed_tables` plus a user-controlled `table` argument would need the full allowlist check.

**Fix:** Either route the generated SQL through the existing safety pipeline (cheapest, consistent):
```python
sql = f"SELECT parameter, PLATFORM_ID, Result FROM {table} WHERE ... LIMIT {ctx.config.row_cap}"
safety = validate_and_sanitize(sql, default_limit=ctx.config.row_cap)
if not safety.ok:
    return ToolResult(content=f"SQL rejected: {safety.reason}")
_check_table_allowlist(safety.sanitized_sql, ctx.config.allowed_tables)
df = ctx.db_adapter.run_query(safety.sanitized_sql)
```
Or use parameterized queries if the DBAdapter exposes them. At minimum, document why the safety gates are intentionally skipped.

---

### WR-04: `get_schema` and `pivot_to_wide` are not covered by `log_query` — OBS-01 gap, not double-logging

**File:** `app/core/agent/tools/get_schema.py:40-60`, `app/core/agent/tools/pivot_to_wide.py:56`
**Issue:** The plan says `get_schema` must NOT double-log by routing through `run_sql` — that invariant is satisfied. However, the plan's OBS-01 intent (audit log per DB interaction) requires that every DB round-trip produce a JSONL entry. `get_schema` fires two `SELECT DISTINCT ...` queries and `pivot_to_wide` fires one wide-form query, and none of them emit a `log_query` entry on success or failure. The audit trail for Phase 2 is therefore incomplete — only `run_sql` calls appear in `logs/queries.log`.

Whether this is a bug or a deliberate scoping decision depends on the plan's OBS-01 wording. If the intent was "log all LLM-issued queries" (including those the agent indirectly triggers via get_schema/pivot_to_wide), these need logging. If the intent was narrower ("only log run_sql's SQL"), documenting that narrowing in the module docstring would help.

**Fix:** Add `log_query(...)` calls wrapping each `ctx.db_adapter.run_query(...)` in `get_schema.py` and `pivot_to_wide.py`, with a `sql` field showing the generated string and a label indicating the source tool (e.g., `user=f"{user} [via get_schema]"`), or confirm in the plan that these are out-of-scope for v1 logging.

---

## Info

### IN-01: `make_chart` and `get_schema_docs` tool classes are missing a `description` attribute

**File:** `app/core/agent/tools/make_chart.py:33-34`, `app/core/agent/tools/get_schema_docs.py:43-47`
**Issue:** The `Tool` Protocol in `_base.py` only requires `name`, `args_model`, and `__call__` — so this is not a protocol violation. But four of the six tools (`run_sql`, `get_schema`, `pivot_to_wide`, `normalize_result`) declare a `description` class attribute that will flow into the OpenAI tool schema, while `make_chart` and `get_schema_docs` do not. When Phase 3 generates the OpenAI `tools=[...]` payload, these two tools will have no top-level description — the LLM will have to infer from the args model docstring alone.

**Fix:** Add a `description` class attribute to both:
```python
class MakeChartTool:
    name = "make_chart"
    args_model = MakeChartArgs
    description = (
        "Render a Plotly chart (bar|line|scatter|heatmap) from a cached "
        "DataFrame identified by data_ref. Returns a rendered chart plus "
        "a short text confirmation."
    )
```

---

### IN-02: `make_chart` reaches into `ctx._df_cache` directly instead of using `ctx.get_df()`

**File:** `app/core/agent/tools/make_chart.py:38`
**Issue:** `AgentContext` exposes `get_df()` / `store_df()` as the public cache API. The leading-underscore `_df_cache` is explicitly private (documented on line 27 of `context.py`). `pivot_to_wide` and `normalize_result` correctly use the public API. `make_chart` uses `ctx._df_cache.get(args.data_ref)`. Functionally equivalent, but violates encapsulation and couples `make_chart` to the dict implementation.

**Fix:** Replace with the public accessor:
```python
df = ctx.get_df(args.data_ref)
```

---

### IN-03: `_truncate_cell` marked `# pragma: no cover` but has non-trivial behavior

**File:** `app/core/agent/tools/run_sql.py:40-44`
**Issue:** `_truncate_cell` is a three-line function that handles `None`, converts to `str`, and conditionally appends a truncation marker. It is covered by the truncation test `test_cell_over_500_chars_is_truncated`. The `# pragma: no cover - trivial` comment is misleading and disables coverage reporting on a function that is tested and observable. If a future edit changes the `500` cap or the `…[truncated]` marker, coverage will silently continue to report 100% despite the change. The truncation-cap value is a SAFE-03 invariant.

**Fix:** Remove the `# pragma: no cover` comment so the function's coverage is counted.

---

### IN-04: `pivot_to_wide.PivotUuidFallbackTest` asserts a length but not determinism

**File:** `tests/core/agent/tools/test_pivot_to_wide.py:93-99`
**Issue:** The test for the uuid4 fallback path asserts only that `result.df_ref` is a non-empty string and that the stored DataFrame is retrievable. It does not assert the collision-resistance property that justifies using uuid4 rather than a deterministic counter. Call twice in the same context — should produce two different keys, both retrievable, with no overwrite. That is the real invariant.

**Fix:** Add a regression test:
```python
def test_two_consecutive_fallback_calls_dont_collide(self):
    ctx = _mk_ctx(_LONG_DF)  # no current_tool_call_id
    r1 = pivot_to_wide_tool(ctx, PivotToWideArgs(category="§3", item="wb_enable"))
    r2 = pivot_to_wide_tool(ctx, PivotToWideArgs(category="§3", item="wb_enable"))
    self.assertNotEqual(r1.df_ref, r2.df_ref)
    self.assertIsNotNone(ctx.get_df(r1.df_ref))
    self.assertIsNotNone(ctx.get_df(r2.df_ref))
```

---

### IN-05: `tests/core/agent/tools/__init__.py` is empty — unittest discovery works, but the file serves no purpose

**File:** `tests/core/agent/tools/__init__.py:1`
**Issue:** The file is present and empty (one-line). Modern pytest/unittest configuration does not require `__init__.py` in test packages unless namespace disambiguation is needed. Keeping it is harmless; removing it would reduce noise in the tests tree. This is purely stylistic — flag only if the project otherwise avoids empty `__init__.py` (the existing `app/__init__.py`, `app/core/__init__.py`, `app/adapters/__init__.py` are described in `CLAUDE.md` as "empty or minimal", so this file is consistent with project conventions after all).

**Fix:** No action required — consistent with project convention. Keep as-is.

---

## Verification Against Focus Areas

| Focus area | Result |
|---|---|
| SAFE-01 bypass paths (subqueries, CTEs, UNION, information_schema, mysql.*) | **FAILED** — CR-01 (CTE body), CR-02 (aliased subquery), CR-03 (LATERAL/Token crash). Direct `information_schema.*`/`mysql.*` access rejected correctly, but indirect access via CTE body with non-forbidden-schema tables passes. |
| SAFE-03 framing envelope integrity | PASS — `_FRAMING_HEADER` prepended before every row payload in `_frame_rows`; empty-DataFrame path also prepends header. Test `test_framing_sentence_exact_byte_match` verifies byte-for-byte match. |
| SAFE-03 500-char per-cell cap via `df.map` (not `applymap`) | PASS — `run_sql.py:50` uses `df.map(_truncate_cell)`; `normalize_result.py:94` uses `src.map(_clean_cell)`. No `applymap` calls anywhere in the tools package. Truncation marker `…[truncated]` present. |
| Prompt injection surface (raw DB content into prompts without framing) | PASS for `run_sql`. **Partial gap:** `get_schema` dumps raw DB distinct values into a JSON payload that will be fed to the LLM as tool content WITHOUT a framing header. A malicious `PLATFORM_ID` value could carry prompt-injection text. Since this returns JSON (not CSV with quoted values), and the model is instructed at the system-prompt level, the real-world risk is lower — but the SAFE-03 invariant is specifically about untrusted-data framing. Consider adding a framing header to `get_schema.py` too, or explicitly documenting the scope of SAFE-03 as "applies to run_sql only". This is not flagged as a finding because the plan language is ambiguous on this point. |
| OBS-01 double-logging (get_schema → run_sql) | PASS — `get_schema.py` calls `ctx.db_adapter.run_query` directly, not `run_sql_tool`. No double logging. (But see WR-04 for single-logging gap.) |
| Cache key hygiene (`current_tool_call_id` + uuid4 fallback) | PASS structurally. One gap flagged as IN-04 (test does not assert non-collision between two consecutive fallback calls). |
| Typo preservation (InfoCatergory vs InfoCategory, SAFE-07) | PASS — `InfoCatergory` (with typo) used consistently in production SQL; `test_no_correct_spelling.py` includes a meta-test that verifies the scanner actually detects injected files. All spec text files use the DB-correct typo. |
| Pydantic 2 correctness (Literal→enum, Field bounds, ConfigDict placement, arbitrary_types_allowed scope) | PASS — empirically verified: `make_chart_type` emits `enum: [bar,line,scatter,heatmap]`; `section` emits `minimum:1, maximum:7`; `arbitrary_types_allowed=True` is only on `ToolResult` (needed for Plotly Figure). `GetSchemaArgs` uses `extra="forbid"` to reject `foo=1`. |
| Korean docstrings on all new modules (head -1) | PASS — all 8 new modules start with a Korean docstring: `run_sql` ("SELECT 전용"), `_allowlist` ("도구용"), `get_schema` ("DB 스키마"), `get_schema_docs` ("UFS 스펙"), `pivot_to_wide` ("long→wide 피벗"), `normalize_result` ("UFS 스펙 §5"), `make_chart` ("차트 생성"), `context.py` ("에이전트 턴 단위"). |
| Test quality — invariants verified vs smoke only | PASS for `run_sql` (`assert_not_called` on all rejection paths, byte-exact framing assertion, log_query count checks). PASS for `pivot_to_wide` (SQL shape asserted, aggfunc='first' dedup verified, SQL quote escape verified). One gap in uuid fallback test noted as IN-04. |
| Import hygiene / module-level side effects | PASS — only `get_schema_docs.py` has a module-level side effect: `_SPEC_DOCS = _load_spec_docs()` reads seven text files from disk at import time. This is the intentional design (O(1) runtime lookup). No other module has unexpected top-level work. |

---

_Reviewed: 2026-04-23_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
