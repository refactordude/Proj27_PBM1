---
phase: 01-foundation
plan: 03
subsystem: agent-tools
tags: [protocol, runtime-checkable, structural-typing, pydantic, tool-contract, unittest]

# Dependency graph
requires:
  - app.core.agent.context.AgentContext (provided by Plan 01-02) — imported for __call__ signature
  - pydantic.BaseModel / ConfigDict / Field (existing Pydantic 2 stack)
  - typing.Protocol / typing.runtime_checkable (stdlib, Python 3.11 native)
provides:
  - Tool Protocol (app/core/agent/tools/_base.py) — structural contract every Phase 2 tool satisfies without inheritance
  - ToolResult Pydantic BaseModel — content + optional df_ref + optional chart envelope
  - @runtime_checkable decorator enabling isinstance(obj, Tool) without TypeError
  - ConfigDict(arbitrary_types_allowed=True) on ToolResult so chart field can hold plotly.graph_objects.Figure
  - Empty package marker app/core/agent/tools/__init__.py (Phase 2 populates with TOOL_REGISTRY)
affects: [01-05-appconfig-integration, 02-tools, 02-tool-registry, 03-agent-loop]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "typing.Protocol + @runtime_checkable for structural typing of tools (no ABC inheritance required)"
    - "Pydantic BaseModel with ConfigDict(arbitrary_types_allowed=True) for envelopes carrying non-Pydantic types (Plotly figures)"
    - "args_model as a type[BaseModel] (class, not instance) so tool.args_model.model_json_schema() fuels TOOL-07 schema generation"
    - "df_ref: str | None as a cache-key indirection — the DataFrame itself lives in AgentContext._df_cache, only the key crosses the loop boundary"
    - "Private-prefix package module _base.py for the contract; package __init__.py intentionally empty until Phase 2 registry lands"

key-files:
  created:
    - app/core/agent/tools/__init__.py
    - app/core/agent/tools/_base.py
    - tests/core/agent/test_tools_base.py
  modified: []

key-decisions:
  - "Tool is a @runtime_checkable typing.Protocol — not an ABC — so Phase 2 tool authors write a class with name/args_model/__call__ and get isinstance(t, Tool)=True for free (structural typing per PEP 544)."
  - "ToolResult stays a flat single-model with Optional fields (content + df_ref + chart), not a discriminated union — make_chart returns BOTH content summary AND chart figure, which a discriminated union would preclude."
  - "df_ref: str | None (not df: pd.DataFrame) — the cache-key indirection keeps DataFrames pinned in AgentContext._df_cache and lets the LLM receive only a lightweight opaque ID."
  - "ConfigDict(arbitrary_types_allowed=True) — required for chart: Any to hold a plotly.graph_objects.Figure; df_ref avoids needing the same flag for pd.DataFrame."
  - "@runtime_checkable is MANDATORY — without it, isinstance(obj, Tool) raises TypeError. Plan explicitly tests this path with assertIsInstance + assertNotIsInstance."
  - "__init__.py left empty — Phase 2 owns TOOL_REGISTRY; keeping the marker empty now prevents import-order surprises when Phase 2 adds sibling tool modules (run_sql.py, inspect_df.py, …)."
  - "Stdlib unittest + unittest.mock.MagicMock, no pytest dependency — matches Plans 01-01 and 01-02 conventions; tests remain pytest-discoverable if the project ever adopts it."

patterns-established:
  - "Structural tool typing: any callable with name: str + args_model: type[BaseModel] + __call__(ctx, args) -> ToolResult IS a Tool — no base class required."
  - "Tool return envelope: always a single ToolResult with content (required, shown to the model) + optional df_ref (AgentContext._df_cache key) + optional chart (Plotly Figure). Failures are modeled as ToolResult(content='<error message>'), not exceptions."
  - "Pydantic 2 arbitrary_types_allowed=True is the escape hatch for non-Pydantic payloads; scoped tightly to fields that need it (chart) rather than blanket-applied."

requirements-completed:
  - AGENT-07

# Metrics
duration: 2m 0s
completed: 2026-04-23
---

# Phase 01 Plan 03: Tool Protocol + ToolResult Summary

**`Tool` @runtime_checkable typing.Protocol and `ToolResult` Pydantic BaseModel landing at `app/core/agent/tools/_base.py`, with 7-test stdlib-unittest coverage proving structural isinstance, negative isinstance, ToolResult defaults, full payload, arbitrary chart types, and toy-tool round-trip through a real AgentContext.**

## Performance

- **Duration:** 2m 0s net coding time (no environment bootstrap needed — pandas/pydantic/pyyaml already installed from Plan 01-02)
- **Started:** 2026-04-22T15:57:32Z
- **Completed:** 2026-04-22T15:59:32Z
- **Tasks:** 2 / 2
- **Files created:** 3
- **Files modified:** 0
- **Tests:** 7 tests, 0 failures, 0 errors (Ran 7 tests in 0.007s, OK)

## Accomplishments

- `Tool` Protocol lands at `app/core/agent/tools/_base.py` with the `@runtime_checkable` decorator (mandatory per RESEARCH.md § Pitfall 2 — without it, `isinstance(obj, Tool)` raises `TypeError`). Structural contract: `name: str`, `args_model: type[BaseModel]` (class, not instance), and `__call__(ctx: AgentContext, args: BaseModel) -> ToolResult`. Phase 2 tool authors write a class with these three attributes — no ABC inheritance, no decorator, nothing else.
- `ToolResult` Pydantic BaseModel with exactly three fields: `content: str` (required — shown to the model), `df_ref: str | None` (optional cache key into `AgentContext._df_cache`), `chart: Any | None` (optional Plotly figure). `model_config = ConfigDict(arbitrary_types_allowed=True)` lets `chart` hold a `plotly.graph_objects.Figure` without Pydantic plumbing, while `df_ref`'s cache-key indirection avoids needing the same flag for `pd.DataFrame`.
- Empty package marker `app/core/agent/tools/__init__.py` (0 lines) — intentional. Phase 2 populates this with `TOOL_REGISTRY` plus individual tool modules; keeping it empty now prevents import-order surprises when sibling modules land.
- `tests/core/agent/test_tools_base.py` ships 7 stdlib-unittest tests across 3 `TestCase` classes, covering every `must_haves.truth` in the plan frontmatter:
  - Truth 1 (Tool importable) — every test imports from `_base`.
  - Truth 2 (ToolResult importable) — every test imports both types.
  - Truth 3 (toy class passes isinstance) — `ToolProtocolTest.test_toy_tool_satisfies_protocol`.
  - Truth 4 (missing `name` fails isinstance) — `ToolProtocolTest.test_missing_name_fails_protocol` (plus a bonus `test_missing_args_model_fails_protocol` catching the symmetric case).
  - Truth 5 (ToolResult.model_dump defaults) — `ToolResultTest.test_defaults`.
  - Truth 6 (chart accepts arbitrary object) — `ToolResultTest.test_arbitrary_chart_allowed`.
  - Plus: `ToolResultTest.test_full_payload` (df_ref round-trip) and `ToolCallIntegrationTest.test_tool_call_returns_tool_result` (full call path through a real `AgentContext(db_adapter=MagicMock(), llm_adapter=MagicMock(), ..., config=AgentConfig())`).
- All 12 Task-1 acceptance criteria and all 10 Task-2 acceptance criteria pass — file existence, `wc -l __init__.py = 0`, Korean docstring on line 1 of `_base.py`, exactly one each of `from __future__ import annotations`, `@runtime_checkable`, `class Tool(Protocol):`, `class ToolResult(BaseModel):`, `model_config = ConfigDict(arbitrary_types_allowed=True)`, `from app.core.agent.context import AgentContext`, `df_ref: str | None`, `chart: Any | None`; 2× `assertNotIsInstance`, 0× `import pytest`, 0× FAIL/ERROR, ≥1× OK.

## Task Commits

Each task was committed atomically on the `gsd` branch:

1. **Task 1: Create `app/core/agent/tools/` package + `_base.py` (Tool Protocol + ToolResult)** — `f4e905c` (feat)
2. **Task 2: Create `tests/core/agent/test_tools_base.py` — SC3 coverage** — `2c38f5b` (test)

Both tasks were `tdd="true"` in the plan, but the `<action>` blocks for each task specified file contents verbatim and ordered implementation first (Task 1) then tests (Task 2). Task-level commits were made in that order and match the plan as written.

## Files Created/Modified

- `app/core/agent/tools/__init__.py` (0 lines) — empty package marker. Phase 2 fills with `TOOL_REGISTRY`.
- `app/core/agent/tools/_base.py` (49 lines) — contains:
  - Module docstring (Korean) calling out structural typing and `model_json_schema()` reuse for TOOL-07.
  - `from __future__ import annotations` header.
  - `ToolResult(BaseModel)` with `ConfigDict(arbitrary_types_allowed=True)` and 3 `Field`-annotated members (`content`, `df_ref`, `chart`).
  - `@runtime_checkable class Tool(Protocol)` with `name: str` attribute, `args_model` as a `@property` returning `type[BaseModel]`, and `__call__(ctx: AgentContext, args: BaseModel) -> ToolResult` signature.
  - Imports `AgentContext` from Plan 01-02's `app/core/agent/context.py` for the `__call__` type hint.
- `tests/core/agent/test_tools_base.py` (86 lines) — 3 `TestCase` classes, 7 tests:
  - `ToolProtocolTest` — `test_toy_tool_satisfies_protocol`, `test_missing_name_fails_protocol`, `test_missing_args_model_fails_protocol`.
  - `ToolResultTest` — `test_defaults`, `test_full_payload`, `test_arbitrary_chart_allowed`.
  - `ToolCallIntegrationTest` — `test_tool_call_returns_tool_result` (uses MagicMock for DB/LLM adapters + real `AgentConfig()`).
  - Module-level `_ToyArgs(BaseModel)` and `_ToyTool` classes serve as the happy-path fixtures.

## Decisions Made

- **Protocol, not ABC.** `typing.Protocol` + `@runtime_checkable` lets tool authors write plain classes — no inheritance, no super() — and still get `isinstance(t, Tool)` for registry-time validation. Existing codebase uses ABCs for `DBAdapter` / `LLMAdapter`, but CONTEXT.md § Fixed by Requirements explicitly mandated `Tool` be a `typing.Protocol`, and RESEARCH.md § Pattern 3 codified the structural-typing rationale. Matches PEP 544's original motivation for Protocol.
- **`@runtime_checkable` is mandatory, not optional.** Confirmed via RESEARCH.md § Pitfall 2: without the decorator, `isinstance(obj, Tool)` raises `TypeError: Instance and class checks can only be used with @runtime_checkable protocols`. The SC3 test (`ToolProtocolTest.test_toy_tool_satisfies_protocol`) would fail at CI time, and Phase 2's `TOOL_REGISTRY` assembly — which will iterate registered tools and call `isinstance(t, Tool)` — would break. The decorator is the non-negotiable fix.
- **`args_model: type[BaseModel]` (class), not an instance.** Phase 2's TOOL-07 generates OpenAI tool schemas via `tool.args_model.model_json_schema()` — a classmethod — so we need the class, not an instance. Exposing it as a `@property` on the Protocol matches how tool classes will typically declare it (`args_model = RunSqlArgs` — a class attribute that Pydantic sees as the schema source).
- **Flat ToolResult with Optional fields, NOT a discriminated union.** Two alternatives were considered in RESEARCH.md § Pattern 3:
  - *Discriminated union* (`ToolResultText | ToolResultChart | ToolResultDfRef`) — more type-safe, but `make_chart` returns BOTH a `content` summary AND a `chart` Figure, which the union would preclude (tools would have to pick one). Rejected.
  - *Single model, Optional fields* (chosen) — `content` is always required, `df_ref` and `chart` default to `None`. Simpler, matches ARCHITECTURE.md § Pattern 2 shape, and handles the mixed-result case naturally.
- **`df_ref: str | None` (cache-key indirection), NOT `df: pd.DataFrame` (inline DataFrame).** The research-flagged shape. Two reasons: (a) DataFrames can be large — serializing one through a ToolResult that's itself serialized for LLM context would blow past `max_context_tokens=30000`; (b) Phase 2's `inspect_df` and `pivot_to_wide` need to refer to a DataFrame the model has already seen, which requires stable identity across tool calls — `AgentContext._df_cache[tool_call_id]` gives that identity, and `df_ref` is the opaque handle the LLM sees.
- **`ConfigDict(arbitrary_types_allowed=True)` tightly scoped to ToolResult.** Pydantic 2 refuses non-Pydantic types in fields by default; a `plotly.graph_objects.Figure` is not a Pydantic type. The config flag is required for `chart: Any | None`. By using `df_ref: str | None` instead of an inline `pd.DataFrame`, we avoid needing the same flag to cover pandas types — scope stays minimal.
- **Empty `__init__.py`, no re-exports.** The plan explicitly forbids populating the package marker with `TOOL_REGISTRY` or even re-exporting `Tool` / `ToolResult` through it — Phase 2 owns `__init__.py`. Consumers here import directly from `app.core.agent.tools._base`. Keeps Phase 2's refactoring surface predictable.
- **stdlib `unittest` + `unittest.mock.MagicMock`, no pytest.** Matches Plans 01-01 and 01-02. `MagicMock()` satisfies the `DBAdapter` / `LLMAdapter` type hints at runtime (Python's dataclasses do not enforce types), so `ToolCallIntegrationTest` can build a real `AgentContext` without needing a live database connection or OpenAI client. Tests remain `python -m unittest discover tests`-compatible.

## Deviations from Plan

None — plan executed exactly as written. File contents in both tasks are verbatim from the `<action>` blocks (Task 1 included a minor cosmetic reformatting of the `Field` arguments across multiple lines for the long `chart` description, still within Pydantic-equivalent semantics — this matches the plan's explicit `<action>` text which also split the `description=(...)` across lines). All 22 combined acceptance criteria (12 Task-1 + 10 Task-2) pass:

- Task 1: `test -f` both files, `wc -l __init__.py = 0`, Korean docstring on head line 1, exactly 1× each of `from __future__ import annotations` / `@runtime_checkable` / `class Tool(Protocol):` / `class ToolResult(BaseModel):` / `model_config = ConfigDict(arbitrary_types_allowed=True)` / `from app.core.agent.context import AgentContext` / `df_ref: str | None` / `chart: Any | None`; `python -c "from app.core.agent.tools._base import Tool, ToolResult; print(ToolResult(content='x').model_dump())"` outputs `{'content': 'x', 'df_ref': None, 'chart': None}`.
- Task 2: `test -f` the test file, exactly 1× each of `import unittest` / `class ToolProtocolTest` / `class ToolResultTest` / `class ToolCallIntegrationTest` / `assertIsInstance(_ToyTool(), Tool)`, exactly 2× `assertNotIsInstance`, 0× `import pytest`, 0 FAIL/ERROR in unittest output, ≥1 `OK`.

No Rule 1/2/3 auto-fixes triggered. No Rule 4 architectural questions raised.

## Issues Encountered

None — environment was already bootstrapped from Plan 01-02 (pandas 3.0.2 + pydantic 2.13.3 + pyyaml 6.0.3 in `.venv/`). All 7 tests passed on the first run. No `requirements.txt` changes, no environment mutations.

## User Setup Required

None — no external service configuration required. Pure type-contract module; nothing to authenticate, no keys to provision, no services to run.

## Threat Model Verification

Plan 01-03 has no `<threat_model>` block — this is a pure type-contract module with no runtime surface, no I/O, no data handling, no auth path. No new network endpoints, no file access, no schema changes at trust boundaries. `Tool` / `ToolResult` cannot spoof anything at runtime because Phase 2's `TOOL_REGISTRY` is a hand-enumerated dict (per RESEARCH.md § Security table) — an arbitrary object cannot inject itself as a tool. No threat flags raised.

## Next Phase Readiness

- **Plan 01-04 (OpenAI timeout fix)** is unaffected — operates on `app/adapters/llm/openai_adapter.py`, no shared files with this plan.
- **Plan 01-05 (AppConfig composition)** is unaffected — mounts `AgentConfig` on `AppConfig.agent`; `Tool` / `ToolResult` are runtime contracts, not config.
- **Phase 2 tools (TOOL-01 through TOOL-06)** are unblocked:
  - Each tool module writes `class RunSqlTool: name = "run_sql"; args_model = RunSqlArgs; def __call__(self, ctx, args) -> ToolResult: ...` — no imports beyond `ToolResult`.
  - Each tool defines its Pydantic `args_model`; `tool.args_model.model_json_schema()` feeds TOOL-07's OpenAI `tools=[...]` schema generator.
  - Tools return `ToolResult(content=..., df_ref=..., chart=...)`. Failure is modeled as `ToolResult(content="<error message>")` — no exception escapes into the agent loop.
- **Phase 2 TOOL-07 (schema generation)** will iterate the `TOOL_REGISTRY` and call `tool.args_model.model_json_schema()` on each tool — a capability enabled precisely by `args_model: type[BaseModel]` on the Protocol.
- **Phase 3 loop controller** can `isinstance(tool, Tool)` at registry-assembly time to catch typos or missing attributes before the loop runs. The `@runtime_checkable` decorator makes this check zero-cost at runtime.
- **Note for Phase 2 planner:** `app/core/agent/tools/__init__.py` is intentionally empty. Phase 2 populates it with `TOOL_REGISTRY = {"run_sql": RunSqlTool(), ...}` and (optionally) re-exports `Tool` / `ToolResult` through the package. Do not assume any re-exports exist today.

## Self-Check

**Files:**

- FOUND: `/home/yh/Desktop/02_Projects/Proj27_PBM1/app/core/agent/tools/__init__.py`
- FOUND: `/home/yh/Desktop/02_Projects/Proj27_PBM1/app/core/agent/tools/_base.py`
- FOUND: `/home/yh/Desktop/02_Projects/Proj27_PBM1/tests/core/agent/test_tools_base.py`

**Commits:**

- FOUND: `f4e905c` — `feat(01-03): add Tool Protocol and ToolResult model`
- FOUND: `2c38f5b` — `test(01-03): cover Tool Protocol isinstance and ToolResult serialization`

**Verification runs:**

- `python -c "from app.core.agent.tools._base import Tool, ToolResult"` → exit 0
- `python -c "..."` (isinstance without TypeError) → `isinstance OK (result=False, no TypeError)`
- `test ! -s app/core/agent/tools/__init__.py` → init.py is empty
- `python -m unittest tests.core.agent.test_tools_base -v` → Ran 7 tests in 0.007s, OK, 0 failures, 0 errors
- Task 1 verification one-liner (isinstance + defaults) → `OK`

---

*Phase: 01-foundation*
*Completed: 2026-04-23*
