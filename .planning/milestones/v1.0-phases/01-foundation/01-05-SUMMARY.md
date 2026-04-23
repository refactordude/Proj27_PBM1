---
phase: 01-foundation
plan: 05
subsystem: config
tags: [pydantic, agent-config, appconfig, yaml, round-trip, session-state-audit, obs-03, unittest]

# Dependency graph
requires:
  - app.core.agent.config.AgentConfig (Plan 01)
provides:
  - AppConfig.agent composed AgentConfig field (OBS-03 YAML surface)
  - YAML round-trip proof via unit tests (backward-compat with old settings.yaml)
  - config/settings.example.yaml documentation of the new app.agent block
  - Phase 4 handoff artifact listing legacy pending_sql keys for HOME-02 removal
  - Prescribed _AGENT_TRACE_KEY = "agent_trace_v1" convention for Phase 4
affects: [04-pages-home, 04-core-session, 04-pages-settings-page]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pydantic submodel composition via Field(default_factory=AgentConfig) for nested YAML"
    - "SETTINGS_PATH env-var override for tempdir-isolated disk round-trip unit tests"
    - "Grep-sourced audit documents as the Phase-to-Phase handoff artifact"

key-files:
  created:
    - tests/core/test_app_config_agent.py
    - .planning/phases/01-foundation/01-05-SESSION-AUDIT.md
  modified:
    - app/core/config.py
    - config/settings.example.yaml

key-decisions:
  - "AppConfig.agent composition via default_factory=AgentConfig (matches existing DatabaseConfig/LLMConfig composition pattern in same module)."
  - "Pydantic default 'ignore' extra-config policy retained — do NOT set extra='forbid' so future YAML additions do not break backward compatibility (RESEARCH.md Pattern 4)."
  - "Explicit path import 'from app.core.agent.config import AgentConfig' (not 'from app.core.agent import ...') to avoid circular-import surprises when Phase 2 populates the tools subpackage."
  - "Settings-UI audit (Option A) confirms no code change needed for OBS-03 — settings_page.py uses hand-written per-field widgets, never iterates model_fields."
  - "Phase 4 new-key convention: _AGENT_TRACE_KEY = 'agent_trace_v1' — versioned suffix future-proofs MEM-01 cross-turn memory; DataFrame cache stays on AgentContext._df_cache per AGENT-07 (no session-state promotion)."

patterns-established:
  - "Composed agent submodel reachable via AppConfig().agent — operators tune budgets by editing config/settings.yaml app.agent.* (v1 YAML-only per OBS-03)."
  - "Audit-only Phase 1 docs land under .planning/phases/01-foundation/<plan>-SESSION-AUDIT.md for the downstream phase planner to consume."

requirements-completed:
  - OBS-03

# Metrics
duration: ~4min
completed: 2026-04-22
---

# Phase 01 Plan 05: AppConfig Composition + Session-State Audit Summary

**`AppConfig` now composes `AgentConfig` via `default_factory=AgentConfig`, the YAML round-trip and backward-compat-with-old-YAML are unit-test-proven, `config/settings.example.yaml` documents the new `app.agent` block, and the Phase 4 handoff audit (`01-05-SESSION-AUDIT.md`) confirms Settings UI compliance with OBS-03 and earmarks `pending_sql` / `pending_sql_edit` for HOME-02 removal.**

## Performance

- **Duration:** ~4 min (per-task net coding time; venv was already warm from Plan 01)
- **Started:** 2026-04-22T16:08:24Z
- **Completed:** 2026-04-22T16:11:52Z
- **Tasks:** 3 / 3
- **Files created:** 2
- **Files modified:** 2

## Accomplishments

- `AppConfig` gains a fifth field `agent: AgentConfig = Field(default_factory=AgentConfig)` at the end of the class definition. Existing four fields (`default_database`, `default_llm`, `query_row_limit`, `recent_query_history`) remain at their original positions and defaults. `Settings`, `load_settings`, `save_settings`, `find_database`, `find_llm`, `DatabaseConfig`, `LLMConfig` are all unchanged.
- `config/settings.example.yaml` documents the new `app.agent:` block with all six AgentConfig field defaults (`model: gpt-4.1-mini`, `max_steps: 5`, `row_cap: 200`, `timeout_s: 30`, `allowed_tables: [ufs_data]`, `max_context_tokens: 30000`). The rest of the example file is byte-for-byte preserved.
- `tests/core/test_app_config_agent.py` proves three independent round-trip guarantees across 6 tests in 3 classes:
  1. In-memory `AppConfig()` defaults match OBS-03 exactly + per-instance `allowed_tables` list independence.
  2. In-memory `Settings()` → `yaml.safe_dump(model_dump)` → `yaml.safe_load` → `Settings.model_validate` round-trip returns an equal object.
  3. Disk round-trip via `SETTINGS_PATH` + `save_settings`/`load_settings` temp-dir isolation — including the explicit backward-compat case of a legacy YAML that has no `app.agent:` key, which still loads with the agent defaults filled in by Pydantic's nested-default fallback.
- `.planning/phases/01-foundation/01-05-SESSION-AUDIT.md` (SC5 Phase 1 deliverable) captures the complete session-state key inventory, grep-sourced evidence for every legacy occurrence, the Phase 4 removal list (`pending_sql` ×7, `pending_sql_edit` ×1), the prescribed `_AGENT_TRACE_KEY = "agent_trace_v1"` convention, the Settings-UI audit finding (Option A — no auto-recursion), and a five-item Phase 4 handoff checklist.
- Plan 01's `AgentConfig` is now reachable from BOTH `app.core.agent.config.AgentConfig` AND `AppConfig().agent` — Phase 1 success criterion 1 is fully integrated.

## Task Commits

Each task was committed atomically:

1. **Task 1: Compose AgentConfig into AppConfig + update settings.example.yaml** — `9240840` (feat)
2. **Task 2: Write tests/core/test_app_config_agent.py** — `0a7ebbf` (test)
3. **Task 3: Audit settings_page.py + produce session-state audit note** — `25052b4` (docs)

## Files Created/Modified

- **Modified** `app/core/config.py`:
  - Added `from app.core.agent.config import AgentConfig` as the last import (line 15), separated by one blank line from the `pydantic` imports per project convention.
  - Added `agent: AgentConfig = Field(default_factory=AgentConfig)` as the last field of `AppConfig` (line 48).
  - Net change: +2 lines.
- **Modified** `config/settings.example.yaml`:
  - Appended a nested `agent:` block (7 lines) as the last child of the existing `app:` block, after `recent_query_history`.
  - Net change: +8 lines.
- **Created** `tests/core/test_app_config_agent.py` (108 lines):
  - `AppConfigAgentFieldTest` — 2 tests: defaults + instance independence
  - `SettingsYamlRoundTripTest` — 2 tests: full in-memory YAML round-trip + old-YAML fallback
  - `SettingsDiskRoundTripTest` — 2 tests: `save_settings`/`load_settings` via `SETTINGS_PATH` env-var override, including a legacy-YAML case
  - Total: 6 tests, 0 failures, 0 errors.
- **Created** `.planning/phases/01-foundation/01-05-SESSION-AUDIT.md` (228 lines):
  - Session-state key inventory table (9 keys)
  - Phase 4 removal list with grep evidence
  - `_AGENT_TRACE_KEY = "agent_trace_v1"` convention + rationale
  - Settings-UI audit (Option A confirmed — no auto-recursion)
  - Phase 1 scope boundary verification
  - Phase 4 handoff checklist (5 items)

## Decisions Made

- **Composition pattern: `default_factory=AgentConfig`.** Same pattern already in use by `Settings.app`, `Settings.databases`, `Settings.llms`, `LLMConfig.headers` — keeps the model consistent and ensures each `AppConfig()` instance gets a fresh `AgentConfig` (no shared mutable state across instances, test-verified).
- **Extra-field policy unchanged.** `AppConfig` inherits Pydantic's default `extra="ignore"`. `extra="forbid"` would reject *any* future YAML addition without a code change — the opposite of the "operators tune YAML independently" contract. Documented in the decision log so Phase 4/5 planners don't tighten this inadvertently.
- **Explicit `app.core.agent.config` import path (not `app.core.agent`).** The `app/core/agent/__init__.py` is intentionally empty (per Plan 01's decision log); importing from the submodule avoids pulling the eventual `tools/` subpackage when Phase 2 populates it, keeping the import surface minimal and sidestepping circular-import risk.
- **`SETTINGS_PATH` env-var override for disk-round-trip tests.** The existing `app/core/config._settings_path()` function already honors `SETTINGS_PATH` — tests leverage that production-code path instead of monkeypatching private constants. Zero test-only code paths in production module.
- **Settings-UI audit: Option A, not Option B.** Grep for `AppConfig|AgentConfig|model_fields|__fields__` on `app/pages/settings_page.py` returned zero hits; the four app-defaults fields are rendered via explicit hand-written widgets. OBS-03 is satisfied by construction — no `if field_name == "agent": continue` guard is needed in Phase 4.
- **`_AGENT_TRACE_KEY = "agent_trace_v1"`, not `"agent_trace"`.** The `_v1` suffix is explicitly future-proofing for MEM-01 (cross-turn memory may change the trace shape). Documented in the audit as a hard constraint on Phase 4.

## Deviations from Plan

None — plan executed exactly as written. All 9+10+12 acceptance criteria across the three tasks passed verbatim; all 6 plan-level success criteria passed; all 8 execution-prompt success criteria passed. The audit document retained Option A (as evidence dictated) and deleted Option B, per the plan's "executor must choose based on evidence" instruction.

## Issues Encountered

None. Environment was already bootstrapped from Plan 01 (the `.venv` with pydantic + pyyaml + pandas + openai + httpx was warm); no secondary installation or workaround was required.

## Auth Gates

None — this plan contains no external service calls.

## Authentication Gates Encountered

None.

## User Setup Required

None — the only operator-facing surface introduced is the YAML `app.agent:` block, which is documented in `config/settings.example.yaml` for anyone copying it into their `config/settings.yaml`.

## Requirements Addressed

- **OBS-03** — fully satisfied:
  - `AgentConfig` is composed into `AppConfig.agent` (this plan Task 1).
  - Budgets are editable via `config/settings.yaml` → `app.agent.*` (YAML round-trip proven in tests).
  - Budgets are NOT editable via the Settings UI (Task 3 audit confirms Option A — no follow-up required).

## Phase 1 SC5 Deliverable

- **Path:** `.planning/phases/01-foundation/01-05-SESSION-AUDIT.md`
- **Contains:**
  - Session-state key inventory (9 active keys across session.py, home.py, compare.py, explorer.py, auth.py)
  - Phase 4 removal list: `pending_sql` (7 occurrences) + `pending_sql_edit` (1 widget key) for HOME-02
  - Prescribed new key: `_AGENT_TRACE_KEY = "agent_trace_v1"` with rationale
  - Settings-UI audit: Option A (no auto-recursion, OBS-03 satisfied by construction)
  - Phase 1 scope-boundary verification (`git diff --name-only` on 5 protected files returns empty)
  - 5-item Phase 4 handoff checklist

## Test Results

```
$ python -m unittest tests.core.test_app_config_agent -v
test_app_config_has_agent_default ... ok
test_each_instance_has_distinct_agent_allowed_tables ... ok
test_load_old_yaml_without_agent_block ... ok
test_save_then_load_preserves_agent ... ok
test_full_round_trip ... ok
test_load_yaml_without_agent_block_falls_back_to_defaults ... ok

Ran 6 tests in 0.035s
OK
```

## Next Phase Readiness

- **Phase 1 is code-complete.** All five plans (`01-01` through `01-05`) have SUMMARY.md files; `AgentConfig`, `AgentContext`, `Tool` protocol + `ToolResult`, OpenAI `httpx.Timeout(30.0)`, and the `AppConfig.agent` composition + audit are all shipped.
- **Phase 2 is fully unblocked.** Tools can import `AgentConfig` from `app.core.agent.config` AND access runtime budgets via `ctx.config.row_cap` / `ctx.config.allowed_tables` (per Plan 02's `AgentContext.config: AgentConfig` wiring). The `Tool` protocol + `ToolResult` are available for implementing `get_schema`, `run_sql`, `summarize_rows`, `make_chart`, `finish`.
- **Phase 4 has its handoff artifact.** When the UI swap begins, the planner will:
  1. Remove `pending_sql` / `pending_sql_edit` from `app/pages/home.py` (HOME-02)
  2. Add `_AGENT_TRACE_KEY = "agent_trace_v1"` to `app/core/session.py`
  3. Preserve `chat_history`, `recent_queries`, `selected_db`, `selected_llm`, `cmp_a`, `cmp_b`, `explorer_df` verbatim (HOME-04, HOME-05)
  4. Re-check `settings_page.py` for any inadvertent introduction of `model_fields` iteration
- **Operators can pre-tune budgets before Phase 2 lands.** They simply copy `config/settings.example.yaml` → `config/settings.yaml` and override any of the six `app.agent.*` values (e.g., lower `row_cap` to 100 for tighter safety during early rollout). Phase 2's tools will consume these values when the loop starts in Phase 3.

## Self-Check

**Files:**
- FOUND: `app/core/config.py` (modified — `agent: AgentConfig` field present at line 48)
- FOUND: `config/settings.example.yaml` (modified — `agent:` block present at lines 37-44)
- FOUND: `tests/core/test_app_config_agent.py` (108 lines, 3 test classes, 6 tests)
- FOUND: `.planning/phases/01-foundation/01-05-SESSION-AUDIT.md` (228 lines, 7 sections)

**Commits:**
- FOUND: `9240840` — `feat(01-05): compose AgentConfig into AppConfig`
- FOUND: `0a7ebbf` — `test(01-05): cover AppConfig.agent composition + YAML round-trip`
- FOUND: `25052b4` — `docs(01-05): add Phase 1 session-state & settings-UI audit`

**Verification runs:**
- `python -c "from app.core.config import AppConfig; c = AppConfig(); assert c.agent.model == 'gpt-4.1-mini'"` → exit 0
- `python -m unittest tests.core.test_app_config_agent -v` → Ran 6 tests, OK, 0 failures, 0 errors
- `grep -c 'agent: AgentConfig' app/core/config.py` → 1
- `git diff --name-only HEAD~3 -- app/pages/home.py app/core/session.py app/pages/settings_page.py app/pages/explorer.py app/pages/compare.py` → empty (scope boundary honored)
- All plan `<must_haves.truths>` (6) independently verified against live code.
- All execution-prompt `<success_criteria>` (8) pass.

## Self-Check: PASSED

---
*Phase: 01-foundation*
*Completed: 2026-04-22*
