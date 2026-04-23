---
phase: 02-tool-implementations
plan: 07
subsystem: agent-tools
tags: [registry, pydantic, protocol, openai-tools, ci-guard, safe-07]

# Dependency graph
requires:
  - phase: 02-tool-implementations
    provides: "run_sql_tool, get_schema_tool, pivot_to_wide_tool, normalize_result_tool, get_schema_docs_tool, make_chart_tool singletons (Wave 1: plans 02-01..02-06)"
provides:
  - "TOOL_REGISTRY: dict[str, Tool] — flat registry with exactly 6 tool entries, importable as `from app.core.agent.tools import TOOL_REGISTRY`"
  - "Registry-shape test suite (5 tests) verifying size, canonical names, Protocol compliance, OpenAI-compatible JSON schemas, name uniqueness"
  - "SAFE-07 CI guard: `test_no_correct_spelling.py` rejects the correctly-spelled `InfoCategory` anywhere under `app/core/agent/**` (production tree only — tests excluded)"
  - "TEST-04 self-meta-test: injects a correct-spelling file, confirms scanner detects it, cleans up via finally, verifies cleanup"
  - "TEST-01 aggregate: full project suite (94 tests, Phase 1 + Phase 2) passes cleanly"
affects: ["03-agent-loop", "04-streamlit-integration"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Flat registry comprehension keyed by tool.name mirrors existing DB/LLM registry pattern"
    - "CI-grep guard with self-meta-test — production-tree scanner + proof-of-detection via temp-file injection"
    - "No-arg Pydantic tool models emit {type:object, properties:{}} — OpenAI-compatible; registry test handles this explicitly"

key-files:
  created:
    - "tests/core/agent/tools/test_registry.py"
    - "tests/core/agent/tools/test_no_correct_spelling.py"
  modified:
    - "app/core/agent/tools/__init__.py (was empty — now exports TOOL_REGISTRY)"

key-decisions:
  - "get_schema tool has an intentionally empty args_model (GetSchemaArgs is a no-arg Pydantic model) — its model_json_schema() produces {type:object, properties:{}}, which is valid for OpenAI no-arg tools. The registry test excludes get_schema from the non-empty-properties assertion via a _NO_ARG_TOOLS set; all other 5 tools retain the non-empty-properties guard."
  - "Scanner uses pathlib.Path.rglob on app/core/agent/ and glob on app/core/agent/tools/spec/*.txt; tests/ directory is NOT traversed (excluded by construction — scanner root is app/core/agent/ only)."
  - "Meta-test uses try/finally for cleanup guarantee even on assertion failure; followed by a post-finally scan asserting cleanup actually worked."

patterns-established:
  - "Tool registry comprehension: `{t.name: t for t in (tool_a, tool_b, ...)}` — matches DB/LLM registry convention"
  - "CI-guard self-verification: every grep-based CI test must have a meta-test that injects a known-bad artifact and proves the scanner catches it"
  - "Pydantic no-arg tools: declare an empty BaseModel with ConfigDict(extra='forbid') — OpenAI accepts {properties:{}} as a no-arg schema"

requirements-completed: [TOOL-07, TOOL-08, SAFE-07, TEST-01, TEST-04]

# Metrics
duration: 3 min
completed: 2026-04-22
---

# Phase 2 Plan 07: TOOL_REGISTRY + CI Guards Summary

**Flat `TOOL_REGISTRY: dict[str, Tool]` wiring all 6 Wave 1 agent tools, plus registry shape/Protocol tests and the SAFE-07 InfoCategory grep guard with a self-meta-test that proves the scanner works.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-22T20:36:34Z
- **Completed:** 2026-04-22T20:40:00Z
- **Tasks:** 4 (3 code + 1 verification)
- **Files modified:** 3 (1 overwritten, 2 created)

## Accomplishments

- `TOOL_REGISTRY` is live and flat — Phase 3 agent loop can do `from app.core.agent.tools import TOOL_REGISTRY` and dispatch by name
- Registry structurally validated: exactly 6 entries, all canonical names, `isinstance(v, Tool)` True for every value, every args_model produces OpenAI-compatible JSON schema
- SAFE-07 CI guard active — any future accidental correctly-spelled `InfoCategory` under `app/core/agent/**` fails CI (the DB column is `InfoCatergory` with typo preserved)
- TEST-04 meta-test proves the scanner is not a no-op: injects a bad file, confirms detection, cleans up, verifies cleanup
- Full suite (94 tests across Phase 1 + Phase 2) passes — TEST-01 aggregate criterion met

## Task Commits

Each task committed atomically:

1. **Task 1: Write TOOL_REGISTRY in app/core/agent/tools/__init__.py** — `58bc3e0` (feat)
2. **Task 2: Registry shape + Protocol compliance test** — `fe5e9e4` (test)
3. **Task 3: InfoCategory grep scanner + self-meta-test** — `6b9b038` (test)
4. **Task 4: Full test suite sanity check** — no commit (pure verification; no files changed)

## Files Created/Modified

- `app/core/agent/tools/__init__.py` — **overwritten** from empty to 24-line module exporting `TOOL_REGISTRY: dict[str, Tool]` built as a comprehension over the 6 Wave 1 tool singletons; Korean module docstring; `__all__ = ["TOOL_REGISTRY"]`.
- `tests/core/agent/tools/test_registry.py` — **created** (52 lines). 5 tests: `test_registry_has_exactly_six_entries`, `test_registry_has_all_canonical_names`, `test_every_value_satisfies_tool_protocol`, `test_every_args_model_produces_openai_compatible_schema`, `test_no_duplicate_names`.
- `tests/core/agent/tools/test_no_correct_spelling.py` — **created** (61 lines). Scanner `_scan_for_correct_spelling()` walks `app/core/agent/**/*.py` + `app/core/agent/tools/spec/*.txt` with regex `\bInfoCategory\b`. 2 tests: `test_production_tree_has_no_correct_spelling` (production-tree guard) and `test_meta_scanner_detects_injected_correct_spelling` (TEST-04 self-meta-test with try/finally cleanup + post-cleanup verification).

## Decisions Made

- **No-arg tool schema handling:** `get_schema` intentionally has an empty args_model (`GetSchemaArgs` with `ConfigDict(extra="forbid")`). Its `model_json_schema()` returns `{"type":"object","properties":{},"title":"GetSchemaArgs"}` — valid OpenAI tool schema. The registry test's OpenAI-compatibility check asserts `properties` is a dict on every tool, but only asserts `len(properties) > 0` for the 5 one-arg+ tools via a `_NO_ARG_TOOLS = {"get_schema"}` exclusion set. This preserves the intent of TOOL-07 (OpenAI-compatible schema) while matching the actual Wave 1 tool design.
- **Scanner scope:** The grep scanner root is `app/core/agent/` — tests/ is excluded by construction (not traversed). Tests legitimately mention the correct spelling when asserting the SAFE-07 rule (e.g., the meta-test's injected string). This matches the plan's CONTEXT.md decision: "tests directory is excluded — tests legitimately mention the correct spelling in assertions."
- **Meta-test cleanup:** Uses try/finally to guarantee `_temp_meta_test.py` is deleted even if an assertion fails mid-test. Followed by a post-finally rescan asserting the production tree is clean (proving cleanup actually worked, not just that the code executed).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Adjusted OpenAI-schema assertion to accommodate no-arg tools**
- **Found during:** Task 2 (registry test execution)
- **Issue:** The plan's verbatim test asserted `self.assertGreater(len(schema["properties"]), 0, ...)` for **every** tool. This failed on `get_schema` because `GetSchemaArgs` is intentionally a no-arg Pydantic model (per plan 02-02's Wave 1 implementation), producing `properties: {}`. The plan's own Wave 1 design explicitly declares `get_schema` as no-arg ("No-arg tool. Pydantic emits {'type':'object'} which OpenAI accepts" — comment in `get_schema.py`), so the Task 2 assertion contradicted the reality established in Wave 1.
- **Fix:** Added a `_NO_ARG_TOOLS = {"get_schema"}` class attribute and guarded the non-empty-properties check behind `if name not in self._NO_ARG_TOOLS`. Kept the `type: object` and `properties is dict` assertions for all tools (these still prove OpenAI compatibility). The spirit of TOOL-07 (valid JSON schema emitted by every args_model) is preserved; the over-strict length check is relaxed only for the one documented no-arg tool.
- **Files modified:** `tests/core/agent/tools/test_registry.py`
- **Verification:** `python -m unittest tests.core.agent.tools.test_registry -v` — all 5 tests pass.
- **Committed in:** `fe5e9e4` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug).
**Impact on plan:** Minimal. The deviation only relaxes one over-strict assertion to match the Wave 1 no-arg design for `get_schema`; the aggregate TOOL-07 guarantee ("every args_model emits OpenAI-compatible JSON schema") is still verified via the preserved `type: object` + `properties: dict` assertions plus the per-tool non-empty check on the other 5 tools. No scope creep; no production-code change.

## Issues Encountered

None during planned work.

## Self-Check

All acceptance criteria verified on disk:
- `[ -f app/core/agent/tools/__init__.py ]` — FOUND
- `[ -f tests/core/agent/tools/test_registry.py ]` — FOUND
- `[ -f tests/core/agent/tools/test_no_correct_spelling.py ]` — FOUND
- `git log --all --oneline | grep '58bc3e0'` — FOUND
- `git log --all --oneline | grep 'fe5e9e4'` — FOUND
- `git log --all --oneline | grep '6b9b038'` — FOUND
- `python -c "from app.core.agent.tools import TOOL_REGISTRY; assert len(TOOL_REGISTRY) == 6"` — PASSED
- `python -m unittest tests.core.agent.tools.test_registry -v` — 5/5 OK
- `python -m unittest tests.core.agent.tools.test_no_correct_spelling -v` — 2/2 OK
- `python -m unittest discover tests` — 94/94 OK
- `ls app/core/agent/_temp_meta_test.py` — not-found (meta-test cleanup verified)
- All 6 TOOL_REGISTRY values: `isinstance(v, Tool) == True` — verified

## Self-Check: PASSED

## Known Stubs

None — every tool in the registry is a fully-wired Wave 1 singleton with working `__call__`. The empty-properties schema for `get_schema` is not a stub but an intentional no-arg design documented in the Wave 1 plan.

## User Setup Required

None — no external service configuration required for this plan.

## Next Phase Readiness

Phase 2 Wave 2 is now complete. All Phase 2 success criteria are met:
- All 6 tools implemented and individually tested (Wave 1)
- Flat TOOL_REGISTRY wired and validated (this plan)
- SAFE-07 CI guard with meta-test active
- Full test suite green (94 tests)

Ready for Phase 3 (agent loop controller, `run_agent_turn`). The agent loop can import `TOOL_REGISTRY` as a single flat dict and dispatch tool calls by name without touching any Wave 1 tool modules.

---
*Phase: 02-tool-implementations*
*Completed: 2026-04-22*
