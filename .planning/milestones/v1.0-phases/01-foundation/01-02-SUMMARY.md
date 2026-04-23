---
phase: 01-foundation
plan: 02
subsystem: agent-context
tags: [dataclass, agent-context, df-cache, dependency-injection, unittest, stateless-per-turn]

# Dependency graph
requires:
  - app.core.agent.config.AgentConfig (provided by Plan 01-01)
  - app.adapters.db.base.DBAdapter (existing)
  - app.adapters.llm.base.LLMAdapter (existing)
provides:
  - AgentContext dataclass (app/core/agent/context.py) — per-turn DI container
  - store_df / get_df helpers for tool-call_id-keyed DataFrame persistence
  - Instance-level _df_cache (field(default_factory=dict)) enforcing AGENT-07
  - Unit test proving ctx1._df_cache is not ctx2._df_cache identity independence
affects: [01-03-tool-protocol, 01-05-appconfig-integration, 02-tools, 03-agent-loop]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "@dataclass with field(default_factory=dict) for mutable instance-level defaults"
    - "Typed abstract-base dependency injection (DBAdapter / LLMAdapter, not concrete adapters)"
    - "stdlib unittest + unittest.mock.MagicMock for adapter stubs in tests"
    - "pd.DataFrame cached by opaque tool_call_id string key"

key-files:
  created:
    - app/core/agent/context.py
    - tests/core/agent/test_context.py
  modified: []

key-decisions:
  - "AgentContext is a @dataclass, not a Pydantic model — pd.DataFrame as a field would force arbitrary_types_allowed=True on Pydantic; CONTEXT.md § Fixed by Requirements mandates dataclass."
  - "_df_cache uses field(default_factory=dict) — bare dict={} default raises ValueError at class decoration time in dataclass; factory form is the canonical AGENT-07 guard."
  - "Adapters are typed as abstract bases (DBAdapter, LLMAdapter), not concrete (MySQLAdapter, OpenAIAdapter) — tools should see only the interface per RESEARCH Pattern 2; any isinstance(OpenAIAdapter) check belongs to Phase 3's loop, not the container."
  - "No token counter, step counter, or trace list on AgentContext — those belong to Phase 3's loop module (CONTEXT.md § Specific Ideas: 'Keep AgentContext lean')."
  - "Stdlib unittest + MagicMock — no pytest dependency (consistent with Plan 01-01); tests remain pytest-auto-discoverable if the project ever adopts it."

patterns-established:
  - "Agent runtime objects that carry DataFrames use @dataclass (not Pydantic) to avoid arbitrary_types plumbing."
  - "All mutable-collection fields on agent dataclasses MUST use field(default_factory=...) — enforced by per-plan SC2-style tests."

requirements-completed:
  - AGENT-07

# Metrics
duration: 2min
completed: 2026-04-22
---

# Phase 01 Plan 02: AgentContext Summary

**AgentContext dataclass with instance-level `_df_cache` (field(default_factory=dict)) satisfying AGENT-07 stateless-per-turn, plus four-test stdlib-unittest coverage proving `ctx1._df_cache is not ctx2._df_cache` at the shape level.**

## Performance

- **Duration:** ~1m 30s net coding time (environment fix — installing pandas into the existing .venv — excluded; see Issues Encountered)
- **Started:** 2026-04-22T15:52:57Z
- **Completed:** 2026-04-22T15:54:28Z
- **Tasks:** 2 / 2
- **Files created:** 2
- **Files modified:** 0
- **Tests:** 4 tests, 0 failures, 0 errors

## Accomplishments

- `AgentContext` lands at `app/core/agent/context.py` as a `@dataclass` with the exact six fields mandated by the plan (`db_adapter`, `llm_adapter`, `db_name`, `user`, `config`, `_df_cache`) plus two helpers (`store_df`, `get_df`). No speculative fields — no token counters, no step counters, no trace lists — per CONTEXT.md § Specific Ideas "Keep AgentContext lean".
- `_df_cache` uses `field(default_factory=dict)` — so every fresh `AgentContext(...)` gets a distinct empty dict, and any future regression to `= {}` would raise `ValueError` at class-decoration time (Python's dataclass guard). This is the non-negotiable AGENT-07 shape.
- Adapters are typed against the abstract bases (`DBAdapter`, `LLMAdapter`) — not against `MySQLAdapter` / `OpenAIAdapter` concrete classes — so Phase 2 tools see only the interface per RESEARCH.md § Pattern 2.
- `tests/core/agent/test_context.py` ships 4 stdlib-unittest tests across 2 `TestCase` classes, covering all 5 `must_haves.truths`:
  - Truth 1 (import) — covered implicitly by every test's `from app.core.agent.context import AgentContext`.
  - Truth 2 (dataclass + default_factory) — `test_fresh_instance_has_empty_cache`.
  - Truth 3 (distinct `_df_cache` identities) — `test_df_cache_is_instance_level` (the SC2 assertion).
  - Truth 4 (store/get round-trip) — `test_store_and_get_df` (identity, not copy).
  - Truth 5 (missing key → None) — `test_get_missing_returns_none`.
- Package sibling layout preserved: `app/core/agent/config.py` (Plan 01-01) and `app/core/agent/context.py` (this plan) now coexist with matching Korean module docstrings. Plan 03 can land `app/core/agent/tools/_base.py` without touching either.

## Task Commits

Each task was committed atomically on the `gsd` branch:

1. **Task 1: Create `app/core/agent/context.py` — AgentContext dataclass** — `76d2e31` (feat)
2. **Task 2: Create `tests/core/agent/test_context.py` — SC2 + AGENT-07 coverage** — `a45774b` (test)

Both tasks were `tdd="true"` in the plan, but the `<action>` block for each task specified file contents verbatim and ordered implementation first (Task 1) then tests (Task 2). Task-level commits were made in that order and match the plan as written.

## Files Created/Modified

- `app/core/agent/context.py` (32 lines) — `@dataclass AgentContext` with:
  - 5 typed input fields: `db_adapter: DBAdapter`, `llm_adapter: LLMAdapter`, `db_name: str`, `user: str`, `config: AgentConfig`.
  - 1 instance cache: `_df_cache: dict[str, pd.DataFrame] = field(default_factory=dict)`.
  - 2 helpers: `store_df(tool_call_id, df) -> None` and `get_df(tool_call_id) -> pd.DataFrame | None`.
  - Korean module docstring explicitly calling out the AGENT-07 stateless-per-turn contract.
- `tests/core/agent/test_context.py` (49 lines) — 2 `TestCase` classes, 4 tests:
  - `AgentContextIsolationTest.test_df_cache_is_instance_level` — stores in one ctx, asserts `get_df` returns `None` in the other AND `assertIsNot(ctx1._df_cache, ctx2._df_cache)`.
  - `AgentContextIsolationTest.test_fresh_instance_has_empty_cache` — `assertEqual(ctx._df_cache, {})` on fresh construction.
  - `AgentContextCacheRoundTripTest.test_store_and_get_df` — `assertIs` after store (identity, not copy).
  - `AgentContextCacheRoundTripTest.test_get_missing_returns_none` — unknown key returns `None`.

## Decisions Made

- **Dataclass, not Pydantic.** `pd.DataFrame` as a Pydantic field requires `model_config = ConfigDict(arbitrary_types_allowed=True)`, plus validators for copy semantics. CONTEXT.md § Fixed by Requirements and ARCHITECTURE.md § Pattern 2 both prescribe a dataclass here; the plan reinforced it; kept as written.
- **Abstract adapter types.** `db_adapter: DBAdapter` (not `MySQLAdapter`) and `llm_adapter: LLMAdapter` (not `OpenAIAdapter`). Tools only ever need the interface; capability checks like "is this the OpenAI adapter so we can use tools API?" belong to the Phase 3 loop controller, not the DI container. Matches RESEARCH.md § Pattern 2 rationale.
- **`_df_cache` uses `field(default_factory=dict)`.** Two reasons: (a) `dict = {}` as a dataclass default raises `ValueError` at class-decoration time — it wouldn't even import — (b) `default_factory=dict` produces a fresh dict per instance, which is the AGENT-07 guarantee. The SC2 test (`assertIsNot(ctx1._df_cache, ctx2._df_cache)`) catches any regression.
- **Private-prefix `_df_cache`, public helpers.** Direct dict mutation is legal in Python and the test reads `_df_cache` directly to assert identity — but every real consumer (Phase 2 tools, Phase 3 loop) goes through `store_df` / `get_df`. The underscore signals "don't touch from outside" without forcing an API change.
- **No `__post_init__`, no `@classmethod` constructors.** Any future need for defensive checks (e.g., "raise if `allowed_tables` is empty") is a Phase 3 concern and should live on the loop entry point, not the container.
- **Stdlib `unittest` + `MagicMock`, no pytest.** Matches Plan 01-01 and RESEARCH.md § Open Questions Q1. `MagicMock()` satisfies `DBAdapter` / `LLMAdapter` type hints at runtime (Python's dataclasses do not enforce types), and tests stay discoverable with `python -m unittest discover tests`.

## Deviations from Plan

None — plan executed exactly as written. File contents in both tasks are verbatim from the `<action>` blocks. All 13 Task-1 acceptance criteria and all 8 Task-2 acceptance criteria pass:

- Task 1: file exists, Korean docstring on line 1, 1× `from __future__ import annotations`, 1× `@dataclass`, 1× `class AgentContext:`, 1× `field(default_factory=dict)`, 1× each adapter/config import, 1× `def store_df`, 1× `def get_df`, 0× forbidden fields (`tokens|trace|step_count`), `dataclasses.is_dataclass(AgentContext)` True.
- Task 2: file exists, 1× `import unittest`, 1× each `TestCase` class, 1× `assertIsNot(ctx1._df_cache, ctx2._df_cache)`, 0× `import pytest`, 0 FAIL/ERROR in unittest output, ≥1 `OK`.

## Issues Encountered

- **Environment bootstrap — pandas not yet installed in the reused `.venv/`.** Plan 01-01 created `.venv/` with `pydantic==2.13.3` + `pyyaml==6.0.3` only; `pandas` was not installed because Plan 01-01 didn't need it. Plan 01-02's test module imports `pandas` (required to construct the `pd.DataFrame` instances that `_df_cache` holds), so `python -m pip install pandas>=2.2` was run inside the existing venv (installed `pandas-3.0.2`, `numpy-2.4.4`, plus transitive `python-dateutil`, `six`). No `requirements.txt` change was made — pandas is already pinned at `pandas>=2.2` in the project's `requirements.txt`, and `.venv/` remains gitignored. Subsequent plans that need `pandas` can reuse this venv without further action.
- **No code deviations from the plan.** All 4 tests pass on the first run; the `<action>` blocks were copied verbatim.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Plan 01-03 (Tool Protocol + ToolResult)** is unblocked — can reference `AgentContext` in the `Tool.__call__(self, ctx: AgentContext, **kwargs)` signature and assume `ctx.config`, `ctx.db_adapter`, `ctx._df_cache` are all safely typed.
- **Plan 01-05 (AppConfig composition)** is unaffected — mounts `AgentConfig` on `AppConfig.agent`; `AgentContext` is a runtime object not a config, so no composition work needed for it.
- **Phase 2 tools** (`run_sql`, `inspect_df`, `pivot_to_wide`, `normalize_result`) now have a typed ctx to accept: `ctx.config.row_cap`, `ctx.config.allowed_tables`, `ctx.db_adapter.run_query(...)`, `ctx.store_df(tool_call_id, df)`, `ctx.get_df(tool_call_id)`. Every interaction point exists.
- **Phase 3 loop controller** can safely rely on AGENT-07: each `home.py` turn constructs a fresh `AgentContext(...)`, and there is no mechanism — no `@classmethod`, no shared class state, no global registry — that would bleed state from a previous turn.

## Self-Check

**Files:**

- FOUND: `/home/yh/Desktop/02_Projects/Proj27_PBM1/app/core/agent/context.py`
- FOUND: `/home/yh/Desktop/02_Projects/Proj27_PBM1/tests/core/agent/test_context.py`

**Commits:**

- FOUND: `76d2e31` — `feat(01-02): add AgentContext dataclass with instance-level _df_cache`
- FOUND: `a45774b` — `test(01-02): cover AgentContext instance-isolation and cache round-trip`

**Verification runs:**

- `python -c "from app.core.agent.context import AgentContext"` → exit 0
- `python -m unittest tests.core.agent.test_context -v` → Ran 4 tests in 0.014s, OK, 0 failures, 0 errors
- Key assertion `ctx1._df_cache is not ctx2._df_cache` → confirmed via standalone script

## Self-Check: PASSED

---
*Phase: 01-foundation*
*Completed: 2026-04-22*
