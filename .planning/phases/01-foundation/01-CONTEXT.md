---
name: Phase 1 Foundation Context
description: Shared contracts (AgentConfig, AgentContext, Tool protocol, ToolResult) + OpenAI timeout fix + session-state hygiene. Pure infrastructure phase — discuss skipped.
phase: 1
status: ready_for_planning
mode: infrastructure_skip
---

# Phase 1: Foundation - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning
**Mode:** Infrastructure phase — smart discuss skipped (no user-facing behavior, purely technical success criteria)

<domain>
## Phase Boundary

The shared contracts that every downstream component imports exist and are correct — `AgentConfig`, `AgentContext`, the `Tool` protocol, `ToolResult`, and the OpenAI timeout fix — so Phase 2 tools can be written and tested in isolation without blocked imports.

Scope is strictly:
- `app/core/agent/config.py` — `AgentConfig` Pydantic model
- `app/core/agent/context.py` — `AgentContext` runtime object (holds `_df_cache` dict per turn)
- `app/core/agent/tools/_base.py` — `Tool` Protocol + `ToolResult` type
- `app/adapters/llm/openai_adapter.py` — add `timeout=httpx.Timeout(30.0)` on every `chat.completions.create`
- Session-state audit: ensure no collision between old Home flow keys (`pending_sql`, legacy chart keys) and upcoming agent trace keys

Out of scope for this phase:
- Any tool implementation (Phase 2)
- Any loop controller logic (Phase 3)
- Any Streamlit UI changes (Phase 4)

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase. Use PROJECT.md, REQUIREMENTS.md (AGENT-07, AGENT-08, AGENT-09, OBS-03), and codebase conventions to guide decisions.

### Fixed by Requirements (not negotiable)
- `AgentConfig` default field values — from REQUIREMENTS.md OBS-03:
  - `max_steps=5`, `row_cap=200`, `timeout_s=30`, `allowed_tables=["ufs_data"]`, `max_context_tokens=30000`, `model="gpt-4.1-mini"`
- `AgentContext` must hold `_df_cache` as an instance-level dict — distinct across instantiations (no shared class-level mutable state).
- `Tool` must be a `typing.Protocol` so any callable matching the signature is structurally compatible — no base-class inheritance required.
- `ToolResult` is a Pydantic model (consistent with existing codebase conventions for multi-value returns; also satisfies `BaseModel.model_json_schema()` usage in TOOL-07 later).
- OpenAI timeout must use `httpx.Timeout(30.0)` and be applied to every `chat.completions.create` call — both `generate_sql` and `stream_text` in `openai_adapter.py`.

### Conventions (follow existing patterns)
- `from __future__ import annotations` at top of every new module.
- `snake_case` for modules/functions, `PascalCase` for Pydantic models.
- Private names `_`-prefixed (e.g., `_df_cache`).
- Module docstrings in Korean (project language, matches existing files like `config.py`).
- Keyword-only public APIs where applicable.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/core/config.py` — existing Pydantic-based `Settings`, `DatabaseConfig`, `LLMConfig`, `AppConfig` models. `AgentConfig` can either (a) live as a new sibling model on `AppConfig`, or (b) live under `app/core/agent/config.py` and be composed into `AppConfig`. Research summary says mount as `AppConfig.agent: AgentConfig` — consistent with existing `DatabaseConfig`/`LLMConfig` composition.
- `app/adapters/llm/openai_adapter.py` — current adapter uses `from openai import OpenAI`; `chat.completions.create` is called in `generate_sql` (line 50) and `stream_text` (line 61). Both need a `timeout=httpx.Timeout(30.0)` kwarg.
- `app/adapters/db/base.py`, `app/adapters/llm/base.py` — existing Protocol-style base classes; use same pattern for `Tool` Protocol.
- `app/adapters/db/registry.py`, `app/adapters/llm/registry.py` — existing flat registry pattern; `TOOL_REGISTRY` in Phase 2 will mirror this but is out of scope here.

### Established Patterns
- `from __future__ import annotations` on every module.
- Pydantic models with `Field(default=..., description=...)` for config values.
- Dataclasses (`SafetyResult`) or Pydantic models (`Settings`) for multi-value returns.
- Module-level private constants prefix with `_` (e.g., `_CHAT_HISTORY_KEY` in `app/core/session.py`).

### Integration Points
- `app/core/config.py` — compose `AgentConfig` into `AppConfig` so operators can set it in `config/settings.yaml`.
- `app/adapters/llm/openai_adapter.py` — add `httpx.Timeout(30.0)` import and kwarg.
- `app/core/session.py` — session-state audit; any new agent trace keys should use a single namespaced prefix (e.g. `_AGENT_TRACE_KEY`).
- New package tree: `app/core/agent/__init__.py`, `app/core/agent/config.py`, `app/core/agent/context.py`, `app/core/agent/tools/__init__.py`, `app/core/agent/tools/_base.py`.

### Dependencies
- `httpx` — already a transitive dependency of `openai`; no new `requirements.txt` entry needed.
- Pydantic 2.7+ — already in stack.

</code_context>

<specifics>
## Specific Ideas

- **Keep `AgentContext` lean.** Only `_df_cache: dict[str, pd.DataFrame]` is required by AGENT-07 + TOOL-03 / TOOL-04 downstream. Do not pre-add fields for "future" memory / token tracking — AGENT-06's token accounting lives in the loop (Phase 3), not the context.
- **Import `httpx` at the top of `openai_adapter.py`.** The research summary specifies `httpx.Timeout(30.0)`. A bare `timeout=30.0` would technically work but deviates from the research-flagged approach; follow the spec.
- **Session-state audit** = grep `app/pages/home.py` and `app/core/session.py` for `pending_sql`, `auto_chart`, and any `result_` prefix; confirm they're either fully scoped (won't collide) or earmarked for Phase 4 deletion. No code removal in Phase 1 — just audit + note in SUMMARY.md.

</specifics>

<deferred>
## Deferred Ideas

None — Phase 1 scope is narrow and mechanical.

</deferred>
