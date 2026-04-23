---
phase: 02-tool-implementations
verified: 2026-04-23T00:00:00Z
status: passed
score: 5/5 success-criteria verified
overrides_applied: 0
requirements_covered: 17/17
---

# Phase 2: Tool Implementations Verification Report

**Phase Goal:** All six agent tools are implemented, safety-hardened, registered in the flat `TOOL_REGISTRY`, and independently tested — meaning Phase 3 can import and dispatch any tool without touching tool code again.

**Verified:** 2026-04-23
**Status:** passed
**Re-verification:** No (initial verification post REVIEW/REVIEW-FIX cycle)

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth (Success Criterion) | Status | Evidence |
|---|---------------------------|--------|----------|
| SC1 | `pytest app/core/agent/tools/` equivalent passes; each of 6 tools has happy + Pydantic arg-failure + domain edge tests | VERIFIED | `python -m unittest discover tests` → Ran 107 tests in 2.227s, OK. Per-tool: test_run_sql (21), test_pivot_to_wide (12), test_normalize_result (13), test_get_schema (6), test_get_schema_docs (5), test_make_chart (7 happy+validation+missing-ref), test_registry (5), test_no_correct_spelling (2) |
| SC2 | `run_sql` rejects `information_schema` / non-allowlisted tables BEFORE DB adapter call; post-fix also rejects CTE bodies + aliased subqueries | VERIFIED | `test_run_sql` 21/21 pass including `test_information_schema_rejected_before_db_call`, `test_cte_body_rejection` (CR-01), `test_aliased_subquery_rejection` (CR-02), `test_no_attribute_error_on_exotic_sql` (CR-03). Direct walker check: `_check_table_allowlist('WITH x AS (SELECT * FROM secret) SELECT * FROM ufs_data', ['ufs_data'])` raises `AllowlistError: Table allowlist violation: ['secret']`. Same for aliased subquery. Both pre-fix bypass vectors now correctly rejected. |
| SC3 | Every `run_sql` ToolResult.content has framing sentence + per-cell 500-char cap | VERIFIED | `grep -c 'untrusted data returned from the database' app/core/agent/tools/run_sql.py` == 1; `test_framing_sentence_exact_byte_match` asserts byte-for-byte prefix match; `test_cell_over_500_chars_is_truncated` asserts `[truncated]` marker; `test_empty_dataframe_framed` covers the empty path. |
| SC4 | `test_no_correct_spelling.py` meta-test works; `InfoCategory` (correct spelling) appears 0 times under `app/core/agent/` | VERIFIED | `python -m unittest tests.core.agent.tools.test_no_correct_spelling` → Ran 2 tests, OK. Both `test_production_tree_has_no_correct_spelling` and `test_meta_scanner_detects_injected_correct_spelling` (TEST-04) pass. `grep -rE '\bInfoCategory\b' app/core/agent/ --include='*.py' --include='*.txt'` returns 0 hits. |
| SC5 | `from app.core.agent.tools import TOOL_REGISTRY` returns dict with exactly 6 entries, each Tool-compliant | VERIFIED | `len(TOOL_REGISTRY) == 6`; sorted keys: `['get_schema', 'get_schema_docs', 'make_chart', 'normalize_result', 'pivot_to_wide', 'run_sql']`. Every value satisfies `isinstance(v, Tool)` (runtime Protocol check). `test_registry` → Ran 5 tests, OK — includes `test_registry_has_exactly_six_entries`, `test_registry_has_all_canonical_names`, `test_every_value_satisfies_tool_protocol`, `test_every_args_model_produces_openai_compatible_schema`, `test_no_duplicate_names`. |

**Score:** 5/5 success criteria verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/core/agent/tools/_allowlist.py` | sqlparse AST walker + forbidden-schema check (SAFE-01) | VERIFIED | Present; `_check_table_allowlist` + `AllowlistError` exported; post-fix recursive descent into every group closes CR-01/CR-02; word-boundary regex for WR-01 |
| `app/core/agent/tools/run_sql.py` | RunSqlTool + run_sql_tool singleton (TOOL-01) | VERIFIED | Imports OK; `isinstance(run_sql_tool, Tool) == True`; framing sentence literal present; `df.map(_truncate_cell)` (not `applymap`); log_query on all 4 exit paths |
| `app/core/agent/tools/get_schema.py` | GetSchemaTool + singleton (TOOL-02) | VERIFIED | Present; uses `InfoCatergory` typo (1 occurrence); JSON output includes all 4 required keys; post-fix log_query wraps the round-trip |
| `app/core/agent/tools/pivot_to_wide.py` | PivotToWideTool + singleton (TOOL-03) | VERIFIED | Present; `aggfunc="first"`; uses `ctx.store_df`; post-fix routes through both safety gates (validate_and_sanitize + _check_table_allowlist) + log_query on all exit paths |
| `app/core/agent/tools/normalize_result.py` | NormalizeResultTool + singleton (TOOL-04) | VERIFIED | Present; `_is_compound` helper (post WR-02 fix requires `=` in every comma-segment); derived cache key `f"{data_ref}:normalized"`; `src.map(_clean_cell)` (not `applymap`) |
| `app/core/agent/tools/get_schema_docs.py` | GetSchemaDocsTool + singleton + `_SPEC_DOCS` loaded at import (TOOL-05) | VERIFIED | Present; `Field(ge=1, le=7)`; `_SPEC_DOCS = _load_spec_docs()` at module level; Tool-compliant |
| `app/core/agent/tools/spec/section_{1..7}.txt` | 7 UFS scaffold spec files | VERIFIED | All 7 files present under `app/core/agent/tools/spec/`; no correct-spelling hits |
| `app/core/agent/tools/make_chart.py` | MakeChartTool + singleton (TOOL-06) | VERIFIED | Present; `Literal["bar","line","scatter","heatmap"]`; uses `plotly.express`; cache lookup via `ctx._df_cache.get` (IN-02 noted but not blocking) |
| `app/core/agent/tools/__init__.py` | TOOL_REGISTRY flat dict (TOOL-08) | VERIFIED | Exports `TOOL_REGISTRY: dict[str, Tool]` with 6 entries, all canonical names; imports all 6 tool singletons |
| `app/core/agent/context.py` | AgentContext + `current_tool_call_id` (added by 02-03) | VERIFIED | New field `current_tool_call_id: str | None = None` added AFTER `config` and BEFORE `_df_cache`; non-breaking; 4 regression tests in `test_context_tool_call_id.py` pass |
| `tests/core/agent/tools/test_*.py` | 6 tool tests + registry + grep (TEST-01, TEST-04) | VERIFIED | All 8 test files present and passing: test_run_sql (21), test_pivot_to_wide (12), test_normalize_result (13), test_get_schema (6), test_get_schema_docs (5), test_make_chart (7), test_registry (5), test_no_correct_spelling (2) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `run_sql.py` | `sql_safety.validate_and_sanitize` | first gate call on raw SQL | WIRED | Called with `default_limit=ctx.config.row_cap`; rejection path returns ToolResult and logs |
| `run_sql.py` | `_allowlist._check_table_allowlist` | second gate call on sanitized SQL | WIRED | Wrapped in `except AllowlistError` + `except Exception` (CR-03 fix) |
| `run_sql.py` | `logger.log_query` | JSONL audit log on all 4 paths | WIRED | Verified: gate-1 reject, gate-2 reject, DB exc, success each emit exactly one log_query call (assertion via MagicMock) |
| `pivot_to_wide.py` | `sql_safety.validate_and_sanitize` + `_check_table_allowlist` | both gates on code-generated SQL (WR-03 fix) | WIRED | Post-fix commit 723ce48 added both gates; `test_safety_gates_invoked` confirms each is called exactly once |
| `pivot_to_wide.py` | `ctx.store_df` / `ctx.current_tool_call_id` | cache wide-form DataFrame keyed by tool_call_id with uuid4 fallback | WIRED | Verified by `PivotHappyPathTest.test_pivots_and_caches` + `PivotUuidFallbackTest` |
| `normalize_result.py` | `ctx.get_df` / `ctx.store_df` | read source DF, write `:normalized` derived key | WIRED | Verified by `DerivedRefFormatTest`, `MissingRefTest` (graceful degradation on missing ref) |
| `get_schema.py` | `ctx.db_adapter.get_schema` + two DISTINCT SELECTs | inspector + filter-candidate surfacing | WIRED | Verified; post-fix single `log_query` call aggregates the 3-query round-trip |
| `get_schema_docs.py` | `_SPEC_DIR / section_{i}.txt` | module-level `read_text` at import | WIRED | `_SPEC_DOCS` populated once; `test_section_3_returns_scaffold_text` asserts non-empty content |
| `make_chart.py` | `plotly.express.{bar,line,scatter,imshow}` | chart-type router | WIRED | All 4 branches covered by `MakeChartHappyPathTest` (bar/line/scatter/heatmap each assert `isinstance(result.chart, go.Figure)`) |
| `tools/__init__.py` | all 6 tool modules | explicit imports building TOOL_REGISTRY | WIRED | All 6 import lines present; dict-comprehension keyed by `.name` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `run_sql.py` | `df` (query result) | `ctx.db_adapter.run_query(sanitized)` | Real (routes through DBAdapter) | FLOWING — framing + per-cell cap applied before return |
| `pivot_to_wide.py` | `df` then `wide` | `ctx.db_adapter.run_query(sanitized)` + `df.pivot_table(...)` | Real | FLOWING — cached via `store_df` |
| `normalize_result.py` | `src` / `normalized` | `ctx.get_df(data_ref)` (populated by prior tool) | Real (reads actual cached DF) | FLOWING |
| `get_schema.py` | `schema`, `df_p`, `df_c` | `ctx.db_adapter.get_schema(...)` + 2 DISTINCT queries | Real (partial fallback on query exception) | FLOWING |
| `get_schema_docs.py` | `_SPEC_DOCS[args.section]` | module-level `read_text` | Real (reads on-disk scaffold text) | FLOWING — non-empty content verified by `test_section_3_returns_scaffold_text` |
| `make_chart.py` | `fig` | `px.{type}(df, ...)` where `df = ctx._df_cache.get(data_ref)` | Real (when cache populated) | FLOWING — `isinstance(fig, go.Figure)` asserted |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite passes | `python -m unittest discover tests` | `Ran 107 tests in 2.227s — OK` | PASS |
| TOOL_REGISTRY has 6 Tool-compliant entries | `python -c "from app.core.agent.tools import TOOL_REGISTRY; from app.core.agent.tools._base import Tool; assert len(TOOL_REGISTRY)==6; [isinstance(v,Tool) for v in TOOL_REGISTRY.values()]"` | sorted keys = `['get_schema','get_schema_docs','make_chart','normalize_result','pivot_to_wide','run_sql']`; all True | PASS |
| CR-01 (CTE body bypass) closed | direct `_check_table_allowlist` call with `WITH x AS (SELECT * FROM secret) SELECT * FROM ufs_data` | raises `AllowlistError: Table allowlist violation: ['secret']` | PASS |
| CR-02 (aliased subquery bypass) closed | direct `_check_table_allowlist` call with `SELECT * FROM (SELECT * FROM secret) ufs_data` | raises `AllowlistError: Table allowlist violation: ['secret']` | PASS |
| SAFE-07 typo guard active | `grep -rE '\bInfoCategory\b' app/core/agent/ --include='*.py' --include='*.txt'` | 0 hits | PASS |
| Framing sentence in run_sql | `grep -c 'untrusted data returned from the database' app/core/agent/tools/run_sql.py` | 1 | PASS |
| run_sql dedicated tests | `python -m unittest tests.core.agent.tools.test_run_sql` | Ran 21 tests, OK | PASS |
| no-correct-spelling meta-test | `python -m unittest tests.core.agent.tools.test_no_correct_spelling` | Ran 2 tests, OK | PASS |
| Registry tests | `python -m unittest tests.core.agent.tools.test_registry` | Ran 5 tests, OK | PASS |

### Requirements Coverage

All 17 phase requirements are declared in at least one PLAN.md `requirements:` frontmatter field, and each has passing verification evidence in the codebase.

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|----------|
| TOOL-01 | 02-01 | `run_sql` — SELECT executor with safety envelope | SATISFIED | `run_sql_tool` singleton; 21 unit tests pass including happy + Pydantic + allowlist + first-gate + framing + truncation + logging |
| TOOL-02 | 02-02 | `get_schema` — tables + distinct PLATFORM_ID + InfoCatergory | SATISFIED | `get_schema_tool` singleton; JSON payload with 4 required keys; 6 unit tests pass; typo preserved |
| TOOL-03 | 02-03 | `pivot_to_wide` — UFS §3 long→wide with cache write | SATISFIED | `pivot_to_wide_tool` singleton; `aggfunc="first"` dedup; both safety gates invoked; 12 unit tests pass |
| TOOL-04 | 02-04 | `normalize_result` — UFS §5 clean_result + compound row-split | SATISFIED | `normalize_result_tool` singleton; hex/int/float/null-likes transformations; compound row-split with `_local`/`_peer` suffix; 13 tests pass (incl WR-02 regression for embedded comma) |
| TOOL-05 | 02-05 | `get_schema_docs` — UFS spec §1–§7 retriever | SATISFIED | `get_schema_docs_tool` singleton; 7 scaffold files on disk; `Field(ge=1, le=7)` bounds; module-level `_SPEC_DOCS`; 5 tests pass |
| TOOL-06 | 02-06 | `make_chart` — Plotly Figure for 4 chart types | SATISFIED | `make_chart_tool` singleton; `Literal` rejects unknown types; all 4 chart_type branches tested; missing-ref graceful error |
| TOOL-07 | 02-01..07 | Every tool's JSON schema from Pydantic `model_json_schema()` | SATISFIED | `test_every_args_model_produces_openai_compatible_schema` in test_registry asserts `type == 'object'` and non-empty `properties` for all 6 args models |
| TOOL-08 | 02-07 | Flat `TOOL_REGISTRY: dict[str, Tool]` in `tools/__init__.py` | SATISFIED | Exactly 6 entries; all canonical names; `test_registry` enforces shape and Protocol compliance |
| SAFE-01 | 02-01 | Allowlist walker blocks non-allowlisted tables | SATISFIED | `_allowlist.py` post-fix recursive descent; closed CR-01 (CTE) and CR-02 (aliased subquery); direct information_schema, mysql, performance_schema, sys all rejected via word-boundary regex (WR-01 fix) |
| SAFE-02 | 02-01 | Auto-LIMIT injection via `validate_and_sanitize` | SATISFIED | `test_happy_path_returns_framed_csv` asserts `"LIMIT 200"` in sanitized SQL passed to adapter |
| SAFE-03 | 02-01 | Untrusted-data framing envelope + 500-char cell cap | SATISFIED | `_FRAMING_HEADER` literal prepended; `_truncate_cell` applies 500-char cap; `test_framing_sentence_exact_byte_match` byte-exact; `test_cell_over_500_chars_is_truncated` |
| SAFE-04 | 02-01 | Existing `sql_safety.validate_and_sanitize` remains first gate | SATISFIED | `run_sql.py` calls `validate_and_sanitize` FIRST before any allowlist or DB call; `test_first_gate_rejection_never_calls_adapter` verifies DDL rejection |
| SAFE-05 | 02-01 | Read-only session enforcement in MySQLAdapter inherited | SATISFIED | Inherited from Phase 1 adapter; `run_sql.py` routes through `ctx.db_adapter.run_query` which enforces readonly when configured |
| SAFE-07 | 02-07 | CI grep test fails on correct `InfoCategory` spelling under app/core/agent/ | SATISFIED | `test_no_correct_spelling.py` with 2 tests (scanner + TEST-04 meta-test); production tree clean (0 hits); typo preserved in get_schema.py (1 hit) and pivot_to_wide.py (1 hit) |
| OBS-01 | 02-01 | `log_query` JSONL entry per `run_sql` execution (all paths) | SATISFIED | `run_sql.py`: 4 log_query call sites (gate-1, gate-2, DB exc, success); `test_log_query_called_on_success`, `test_log_query_called_on_allowlist_rejection`, `test_log_query_called_on_first_gate_rejection` assert exactly-one invocation; post-WR-04 fix `get_schema` and `pivot_to_wide` also log |
| TEST-01 | 02-07 | Each of 6 tools has happy + Pydantic + domain-edge tests | SATISFIED | All 6 tools have ≥3 test classes; aggregate 73 tool tests pass; full suite 107 tests pass |
| TEST-04 | 02-07 | CI grep for correct `InfoCategory` spelling under app/core/agent/ | SATISFIED | `test_meta_scanner_detects_injected_correct_spelling` injects temp file, asserts scanner catches it, cleans up in `finally` block, confirms post-cleanup clean state |

**Coverage:** 17/17 phase requirements satisfied. No orphaned requirements.

### Anti-Patterns Found

None that block the phase goal. Prior REVIEW-FIX already closed all 3 Critical issues (CR-01 CTE bypass, CR-02 aliased subquery bypass, CR-03 LATERAL Token crash) and all 4 Warnings (WR-01 substring false positives, WR-02 compound-split row loss, WR-03 pivot safety gates, WR-04 OBS-01 logging gaps). Review info items (IN-01..05) are cosmetic/style and were explicitly out of scope for the fix iteration.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `make_chart.py` | ~40 | `ctx._df_cache.get(args.data_ref)` private-attribute access instead of `ctx.get_df()` (IN-02) | Info | Functionally equivalent; documented in REVIEW.md as non-blocking encapsulation nit |
| `run_sql.py` | _truncate_cell | `# pragma: no cover - trivial` on a tested function (IN-03) | Info | Coverage tooling may underreport; behavior is correct and tested |

Neither is a blocker. No TODO/FIXME/XXX/HACK/PLACEHOLDER comments found in the phase's shipped production files that affect goal achievement.

### Human Verification Required

None. All success criteria are verified programmatically through the test suite.

### Gaps Summary

No gaps. Phase 2 achieves its roadmap goal: "All six agent tools are implemented, safety-hardened, registered in the flat `TOOL_REGISTRY`, and independently tested — meaning Phase 3 can import and dispatch any tool without touching tool code again."

- Six tools present: `run_sql`, `get_schema`, `pivot_to_wide`, `normalize_result`, `get_schema_docs`, `make_chart`
- Each tool satisfies the `Tool` Protocol (runtime structural check)
- Each tool has Pydantic-generated JSON schema suitable for OpenAI `tools=[...]`
- Safety hardening verified: allowlist walker closes known bypass vectors (CR-01/CR-02/CR-03), run_sql framing + 500-char cell cap, pivot_to_wide routes through both safety gates (WR-03 fix)
- `TOOL_REGISTRY` is a flat `dict[str, Tool]` with exactly 6 entries — Phase 3 can `from app.core.agent.tools import TOOL_REGISTRY` and dispatch
- Test suite aggregates 107 passing tests; no regressions in Phase 1 tests
- SAFE-07 typo guard is active with a TEST-04 meta-test proving the scanner detects injected violations

Phase 2 is ready for Phase 3 (Agent Loop Controller) to consume.

---

_Verified: 2026-04-23_
_Verifier: Claude (gsd-verifier)_
