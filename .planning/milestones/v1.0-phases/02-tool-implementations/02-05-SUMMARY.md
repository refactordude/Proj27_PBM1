---
phase: 02-tool-implementations
plan: 05
subsystem: api
tags: [pydantic, pathlib, unittest, tools, ufs-spec]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Tool Protocol, ToolResult model, AgentContext
provides:
  - get_schema_docs_tool singleton exporting the Tool Protocol shape (name, args_model, __call__)
  - GetSchemaDocsArgs Pydantic model bounding section ∈ [1, 7] via Field(ge=1, le=7) — bounds surface in OpenAI JSON schema
  - Module-level _SPEC_DOCS dict loaded once at import via _load_spec_docs() — O(1) subsequent reads
  - Seven UFS spec scaffold text files (section_1.txt .. section_7.txt) with §N headers + Phase 5 TODO placeholders; §3 and §5 include one-sentence semantic hints
affects: [02-07-registry, 03-agent-loop, 05-final-ship]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-level eager loading: read-once at import, O(1) memory hits for subsequent calls (matches RESEARCH.md §Tool 5 pattern)"
    - "Tool + spec co-location: spec data lives at app/core/agent/tools/spec/ next to its single consumer get_schema_docs.py"
    - "Graceful fallback on missing files: _load_spec_docs returns '(section_N.txt missing — not yet authored)' instead of raising — keeps module importable even if a scaffold file is deleted"

key-files:
  created:
    - app/core/agent/tools/get_schema_docs.py
    - app/core/agent/tools/spec/section_1.txt
    - app/core/agent/tools/spec/section_2.txt
    - app/core/agent/tools/spec/section_3.txt
    - app/core/agent/tools/spec/section_4.txt
    - app/core/agent/tools/spec/section_5.txt
    - app/core/agent/tools/spec/section_6.txt
    - app/core/agent/tools/spec/section_7.txt
    - tests/core/agent/tools/test_get_schema_docs.py
  modified: []

key-decisions:
  - "Spec files ship as scaffolds with §N headers + Phase 5 TODO notes (per CONTEXT.md §Claude's Discretion) — final UFS spec text is Phase 5 ship-bar work"
  - "Sections §3 (pivot) and §5 (compound split) include a one-sentence semantic hint so early agent runs can still answer spec-lookup questions meaningfully even with scaffold text"
  - "Module-level eager load chosen over lazy first-call load — one disk read at import is cheaper than branching on every tool call and matches the RESEARCH.md §Tool 5 locked pattern"

patterns-established:
  - "Eager-load at import + fallback on missing file: applies to any future tool that reads a fixed file set (see _load_spec_docs)"
  - "Single-file tool module: Pydantic args model + tool class + singleton instance colocated in the tool's .py file (matches run_sql, get_schema, pivot_to_wide, normalize_result conventions)"

requirements-completed: [TOOL-05, TOOL-07]

# Metrics
duration: ~2min
completed: 2026-04-23
---

# Phase 2 Plan 05: get_schema_docs Summary

**On-demand UFS spec §1–§7 retriever with module-level eager-load cache, Pydantic-bounded section arg, and 7 scaffold text files ready for Phase 5 authoring.**

## Performance

- **Duration:** ~2min (3 commits spanning 05:27:56 → 05:29:38 +0900)
- **Started:** 2026-04-22T20:27:56Z
- **Completed:** 2026-04-22T20:29:38Z
- **Tasks:** 2 (Task 1 scaffold files, Task 2 tool module + tests)
- **Files created:** 9 (1 tool module, 7 scaffold text files, 1 test module)
- **Files modified:** 0

## Accomplishments
- `get_schema_docs_tool` importable and satisfies the `Tool` Protocol (`isinstance(get_schema_docs_tool, Tool)` passes).
- Seven UFS spec scaffold files land at `app/core/agent/tools/spec/` with correct §N headers and Phase 5 TODO placeholders. Sections §3 and §5 include one-sentence semantic hints (pivot_table / compound split) so the agent can produce useful answers even pre-Phase-5.
- `_SPEC_DOCS` is loaded exactly once at module import — tool calls are O(1) dict lookups with zero disk I/O on the hot path.
- Pydantic `Field(ge=1, le=7)` rejects `section=0` and `section=8` with `ValidationError`, and the bound is carried into the OpenAI JSON schema automatically via `BaseModel.model_json_schema()` (foundation for TOOL-07).
- All 5 unit tests pass (happy path × 2, bounds failure × 2, missing-file edge × 1).
- SAFE-07 preserved: zero correctly-spelled `InfoCategory` occurrences under `app/core/agent/tools/`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create 7 UFS spec scaffold files** — `922acf5` (feat)
2. **Task 2a: Add failing tests for get_schema_docs (RED)** — `324b5a6` (test)
3. **Task 2b: Implement get_schema_docs tool (GREEN)** — `6769497` (feat)

_Task 2 used TDD: test commit first (RED, ModuleNotFoundError), then implementation commit (GREEN, 5/5 pass). No REFACTOR needed — module was clean on first pass._

## Files Created/Modified

- `app/core/agent/tools/get_schema_docs.py` — Tool module: `_SPEC_DIR`, `_load_spec_docs()`, module-level `_SPEC_DOCS`, `GetSchemaDocsArgs` (Field ge=1 le=7), `GetSchemaDocsTool`, `get_schema_docs_tool` singleton. Korean module docstring.
- `app/core/agent/tools/spec/section_1.txt` — §1 UFS Benchmark Overview scaffold.
- `app/core/agent/tools/spec/section_2.txt` — §2 Table Schema (ufs_data) scaffold; reminds authors that `InfoCatergory` typo is intentional per SAFE-07.
- `app/core/agent/tools/spec/section_3.txt` — §3 Long→Wide Pivot scaffold + `df.pivot_table(aggfunc="first")` summary hint.
- `app/core/agent/tools/spec/section_4.txt` — §4 Units and Scaling scaffold.
- `app/core/agent/tools/spec/section_5.txt` — §5 clean_result / Compound Values scaffold + `local=…,peer=…` → `_local`/`_peer` summary hint.
- `app/core/agent/tools/spec/section_6.txt` — §6 Error Sentinels scaffold.
- `app/core/agent/tools/spec/section_7.txt` — §7 Device Naming Conventions scaffold.
- `tests/core/agent/tools/test_get_schema_docs.py` — 3 TestCase classes, 5 tests: happy path (§3 header + "not yet authored" absent), protocol fields, section=0 rejection, section=8 rejection, missing-file edge via `patch.dict(_SPEC_DOCS, {5: ...})`.

## Decisions Made

- **Compact `Field(..., ge=1, le=7, description=...)` on one line** instead of a multi-line form — matches the plan's acceptance grep (`grep -c 'ge=1, le=7'` == 1) and keeps the model definition readable.
- **No `sys`/`performance_schema`-style forbidden-key handling for spec IDs** — Pydantic `ge=1, le=7` already closes the entire invalid space; adding a forbidden set would be redundant.
- **`ctx` parameter kept in `__call__` signature** even though `get_schema_docs` does not consume any context fields — required by the `Tool` Protocol so dispatch stays uniform across all six tools in Phase 3.
- **Spec file extension `.txt`** (not `.md`) — the content is read verbatim and streamed back to the model; no renderer in the loop means no benefit from markdown, and plain text keeps parsing rules obvious.

## Deviations from Plan

None — plan executed exactly as written.

**Total deviations:** 0
**Impact on plan:** Plan 02-05 was the smallest of the six tool plans (two tasks, ~2 min) and was fully specified with verbatim file contents and test code. Zero rule invocations needed.

## Issues Encountered

- **One near-miss:** My first implementation spread `Field(..., ge=1, le=7, description=...)` across multiple lines, which broke the plan's `grep -c 'ge=1, le=7' == 1` acceptance check (returned 0). I collapsed the call onto a single line to match the exact grep form specified by the plan. No functional change — just a style adjustment to satisfy the literal acceptance grep. Not counted as a deviation because the tool's behavior was never wrong.

## Known Stubs

The seven `section_N.txt` files are **intentional scaffolds**, flagged per CONTEXT.md §Claude's Discretion:

- `spec/section_1.txt` through `spec/section_7.txt` — each contains a §N header + "TODO: Final UFS spec §N text to be authored by domain experts in Phase 5." Sections §3 and §5 additionally include a one-sentence semantic hint so the agent is not fully blind pre-Phase 5.
- **Resolution phase:** Phase 5 (final ship) — domain experts author final UFS spec text in-place. The loader, tool, tests, and registry wiring do not change.
- **Why this is safe now:** `get_schema_docs` works end-to-end today with scaffold text; Phase 3's loop can call it and receive deterministic content. Phase 5 is a content-swap, not a code change.

## User Setup Required

None — no external service configuration required. The tool reads local files bundled with the repo.

## Next Phase Readiness

- **Plan 02-06 (make_chart) can run in parallel to this plan** — no shared files.
- **Plan 02-07 (TOOL_REGISTRY + SAFE-07 grep test)** can now pick up `get_schema_docs_tool` from `app.core.agent.tools.get_schema_docs` and wire it into the flat `TOOL_REGISTRY` dict (this is the last ingredient needed from plan 02-05 for the registry).
- **Phase 3 (agent loop)** can import `get_schema_docs_tool`, pass a validated `GetSchemaDocsArgs(section=N)`, and receive `ToolResult(content=<text>)` immediately — no further work on this tool is required for Phase 3.
- **Phase 5 (final ship)** needs to author the final UFS spec text into the 7 scaffold files; the file paths, filenames, and loader code are all frozen.
- **No blockers** for downstream work.

## Self-Check: PASSED

All claimed files exist on disk:
- FOUND: app/core/agent/tools/get_schema_docs.py
- FOUND: app/core/agent/tools/spec/section_{1..7}.txt (7 files)
- FOUND: tests/core/agent/tools/test_get_schema_docs.py

All claimed commits exist in history:
- FOUND: 922acf5 (Task 1 — scaffold files)
- FOUND: 324b5a6 (Task 2 RED — failing test)
- FOUND: 6769497 (Task 2 GREEN — tool implementation)

All 5 unit tests pass: `python -m unittest tests.core.agent.tools.test_get_schema_docs -v` → OK.

SAFE-07 grep: `grep -rc '\bInfoCategory\b' app/core/agent/tools/spec/` returns 0 across all 7 files.

Tool Protocol conformance: `isinstance(get_schema_docs_tool, Tool)` returns True.

---
*Phase: 02-tool-implementations*
*Plan: 05*
*Completed: 2026-04-23*
