---
phase: 01-foundation
plan: 01
subsystem: config
tags: [pydantic, agent-config, agent-budgets, openai, unittest, yaml]

# Dependency graph
requires: []
provides:
  - app.core.agent package namespace for agent subsystem
  - AgentConfig Pydantic model with OBS-03 budget defaults (max_steps=5, row_cap=200, timeout_s=30, max_context_tokens=30_000)
  - Model selector field (gpt-4.1-mini default, swappable via YAML per AGENT-09)
  - allowed_tables allowlist seeded with ["ufs_data"]
  - tests/ package tree (tests/, tests/core/, tests/core/agent/) ready for subsequent phase 1 plans
  - AgentConfig bounds (ge/le) enforced via pydantic.ValidationError
affects: [01-02-context, 01-03-tool-protocol, 01-05-appconfig-integration, 02-tools, 03-agent-loop]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pydantic BaseModel with Field(default=..., ge=..., le=...) for budget fields"
    - "default_factory=lambda: [...] for instance-level mutable list defaults"
    - "stdlib unittest test modules (no pytest dep) — still pytest-compatible"
    - "tests/<mirror-of-app>/ directory layout for unittest auto-discovery"

key-files:
  created:
    - app/core/agent/__init__.py
    - app/core/agent/config.py
    - tests/__init__.py
    - tests/core/__init__.py
    - tests/core/agent/__init__.py
    - tests/core/agent/test_config.py
  modified: []

key-decisions:
  - "AgentConfig lives in app/core/agent/config.py (not inlined in app/core/config.py) to match existing adapter/package layering and keep Phase 5 composition (AppConfig.agent) a pure mount."
  - "Field model is plain str (not Literal) so operators can swap models via YAML without code changes (AGENT-09)."
  - "Stdlib unittest for tests — pytest is not in requirements.txt; unittest classes remain pytest-auto-discoverable."
  - "No model-level validators or ConfigDict added — keep model minimal per CONTEXT.md 'Keep AgentContext lean' guidance (same rule applies to AgentConfig)."

patterns-established:
  - "Agent subsystem modules land under app/core/agent/** with Korean module docstrings matching app/core/config.py."
  - "Each agent Pydantic model gets a paired tests/core/agent/test_*.py covering defaults, bounds, YAML round-trip, and instance independence."

requirements-completed:
  - AGENT-09
  - OBS-03

# Metrics
duration: 2min
completed: 2026-04-22
---

# Phase 01 Plan 01: AgentConfig Foundation Summary

**Pydantic AgentConfig model exposing every per-turn agent budget (max_steps=5, row_cap=200, timeout_s=30, max_context_tokens=30_000), the ufs_data allowlist, and the swappable gpt-4.1-mini model selector — all with ge/le bounds and full stdlib-unittest coverage.**

## Performance

- **Duration:** ~2 min (net coding time; environment bootstrap — creating a local venv and installing pydantic/pyyaml — excluded)
- **Started:** 2026-04-22T15:47:45Z
- **Completed:** 2026-04-22T15:49:20Z
- **Tasks:** 2 / 2
- **Files created:** 6
- **Files modified:** 0

## Accomplishments

- `app/core/agent/` subpackage exists with a documented Korean module header and empty `__init__.py`, establishing the namespace that Plans 02–05 will populate (`context.py`, `tools/_base.py`) and Plan 05 will mount onto `AppConfig`.
- `AgentConfig` Pydantic model ships with all six fields at the OBS-03 / AGENT-09 defaults — `model="gpt-4.1-mini"`, `max_steps=5`, `row_cap=200`, `timeout_s=30`, `allowed_tables=["ufs_data"]`, `max_context_tokens=30_000` — and enforces `ge/le` bounds so operators cannot misconfigure budgets out of safe ranges via YAML.
- `tests/core/agent/test_config.py` covers all 5 plan truths (SC1): defaults, YAML round-trip, six explicit out-of-range rejections across four fields, and instance-level `allowed_tables` independence (default_factory verified). 9 tests, 0 failures, 0 errors.
- `tests/` tree now exists with `__init__.py` markers, so future phase-1 plans (context, tool protocol, openai timeout) can drop their test modules into `tests/core/agent/` or `tests/adapters/llm/` and be picked up by `python -m unittest discover tests`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create `app/core/agent/` package + AgentConfig Pydantic model** — `2ff96ed` (feat)
2. **Task 2: Create `tests/core/agent/test_config.py` — SC1 coverage** — `6120d00` (test)

_Note: Both tasks carried `tdd="true"`, but the plan's `<action>` blocks ordered implementation first and tests second (Task 1 = model, Task 2 = tests). Task-level commits were made in that order and match the plan as written; the model therefore passed its own `<verify>` block before the test file existed._

## Files Created/Modified

- `app/core/agent/__init__.py` — Empty package marker; intentionally exports nothing so downstream imports remain explicit per CONVENTIONS.md § Module Design.
- `app/core/agent/config.py` — `AgentConfig(BaseModel)` with six fields (`model`, `max_steps`, `row_cap`, `timeout_s`, `allowed_tables`, `max_context_tokens`), `ge`/`le` bounds on all numeric fields, `default_factory=lambda: ["ufs_data"]` for the allowlist, and a Korean module + class docstring.
- `tests/__init__.py`, `tests/core/__init__.py`, `tests/core/agent/__init__.py` — Empty package markers enabling `python -m unittest discover tests`.
- `tests/core/agent/test_config.py` — Three `TestCase` classes (`AgentConfigDefaultsTest`, `AgentConfigBoundsTest`, `AgentConfigInstanceIndependenceTest`) covering 9 tests: field defaults, `model_dump → yaml.safe_dump → yaml.safe_load → model_validate` round-trip, six bound-rejection cases, and two-instance `allowed_tables` independence.

## Decisions Made

- **Where `AgentConfig` lives.** Placed in `app/core/agent/config.py` rather than inlined into `app/core/config.py`. Rationale: mirrors the adapter/package split already used by `app/adapters/db/*` and `app/adapters/llm/*`, keeps the agent subsystem self-contained, and makes Plan 05's `AppConfig.agent: AgentConfig` composition a single-line mount on existing `Settings` plumbing.
- **`model` typed as `str`, not `Literal`.** AGENT-09 explicitly calls for operator-controlled model escalation (gpt-4.1-mini ↔ gpt-4.1). A `Literal` would force a code change for that swap; a bounded `str` lets YAML drive it and is trivially validated at call sites.
- **Stdlib unittest over pytest.** Matches RESEARCH.md Q1 — `pytest` is not in `requirements.txt`, and unittest-style `TestCase` classes are auto-discovered by pytest if the project ever adopts it. Zero new deps; full CLAUDE.md "no new frameworks" compliance.
- **Model kept intentionally minimal.** No `ConfigDict`, no model-level validators, no `@field_validator` additions beyond `ge/le`. CONTEXT.md § Specific Ideas mandates "keep AgentContext lean"; the same guidance applies to AgentConfig — Phase 3's loop controller is the right place for any cross-field checks.

## Deviations from Plan

None — plan executed exactly as written. The six files, ten Task-1 acceptance criteria, eleven Task-2 acceptance criteria, and all five `must_haves.truths` pass verbatim.

## Issues Encountered

- **Environment bootstrap (not a plan deviation).** The host `python3` (`/usr/bin/python3`) had no `pip`, no `ensurepip`, and no `pydantic` / `pyyaml` installed — so the plan's `<verify>` and `<acceptance_criteria>` Python commands could not run. Bootstrapped a local `.venv/` (via `python3 -m venv --without-pip`), downloaded `get-pip.py` from `bootstrap.pypa.io`, installed `pydantic>=2.7` (2.13.3) + `pyyaml>=6.0` (6.0.3) into the venv, and ran every verify/acceptance command through `./.venv/bin/python`. `.venv/` is already in `.gitignore`, so nothing leaks into the repo. Subsequent plans can reuse this venv or spin up their own — no code change was required.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Plan 02 (AgentContext)** is unblocked — `app.core.agent` namespace exists; context module can land as a sibling of `config.py`.
- **Plan 03 (Tool protocol + ToolResult)** is unblocked — can consume `AgentConfig` in its `ctx` type if desired; Pydantic infrastructure is warm.
- **Plan 05 (AppConfig composition)** has the exact model it needs; composition is a one-line `agent: AgentConfig = Field(default_factory=AgentConfig)` addition to `app/core/config.AppConfig`.
- **Phase 2 tools** can reliably import `ctx.config.row_cap` and `ctx.config.allowed_tables` once Plan 02 wires `AgentContext.config: AgentConfig`. No further Plan-01 work required.

## Self-Check

**Files:**
- FOUND: `app/core/agent/__init__.py`
- FOUND: `app/core/agent/config.py`
- FOUND: `tests/__init__.py`
- FOUND: `tests/core/__init__.py`
- FOUND: `tests/core/agent/__init__.py`
- FOUND: `tests/core/agent/test_config.py`

**Commits:**
- FOUND: `2ff96ed` — `feat(01-01): add AgentConfig Pydantic model for agent loop budgets`
- FOUND: `6120d00` — `test(01-01): cover AgentConfig defaults, bounds and YAML round-trip`

**Verification runs:**
- `python -c "from app.core.agent.config import AgentConfig"` → exit 0
- `python -c "AgentConfig()"` → defaults match OBS-03 verbatim
- `python -m unittest tests.core.agent.test_config -v` → Ran 9 tests, OK, 0 failures, 0 errors
- All 5 `must_haves.truths` independently verified by a standalone script (see execution log)

## Self-Check: PASSED

---
*Phase: 01-foundation*
*Completed: 2026-04-22*
