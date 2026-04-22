---
phase: 01-foundation
reviewed: 2026-04-23T00:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - app/core/agent/__init__.py
  - app/core/agent/config.py
  - app/core/agent/context.py
  - app/core/agent/tools/__init__.py
  - app/core/agent/tools/_base.py
  - app/core/config.py
  - app/adapters/llm/openai_adapter.py
  - config/settings.example.yaml
  - tests/__init__.py
  - tests/core/__init__.py
  - tests/core/agent/__init__.py
  - tests/core/agent/test_config.py
  - tests/core/agent/test_context.py
  - tests/core/agent/test_tools_base.py
  - tests/core/test_app_config_agent.py
  - tests/adapters/__init__.py
  - tests/adapters/llm/__init__.py
  - tests/adapters/llm/test_openai_timeout.py
findings:
  critical: 0
  warning: 1
  info: 3
  total: 4
status: issues_found
---

# Phase 01-foundation: Code Review Report

**Reviewed:** 2026-04-23T00:00:00Z
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

Phase 1 establishes the agent-engine scaffolding: `AgentConfig` Pydantic model, `AgentContext` dataclass DI container, `Tool` Protocol + `ToolResult` model, `AppConfig.agent` composition, example YAML, and a 30-second `httpx.Timeout` wired into both OpenAI call sites. All eight production files and ten test files were reviewed at standard depth with Python 3.11 / Pydantic 2 / `typing.Protocol` correctness as the focus.

Overall assessment is strong. Pydantic v2 mutable-default hazards are correctly avoided (`Field(default_factory=lambda: ["ufs_data"])` for `allowed_tables`, `field(default_factory=dict)` for `_df_cache`), and both invariants are backed by concrete instance-independence tests rather than smoke tests. The `@runtime_checkable` `Tool` Protocol is exercised with both positive and negative `isinstance` cases. The `httpx.Timeout` is verified via `call_args.kwargs` inspection on both `generate_sql` and `stream_text`, confirming it is passed as the `timeout=` kwarg (not just constructed). The Korean docstring in `openai_adapter.py` is preserved — the diff only appends one new Korean line and adds two import/constant lines; no existing lines were rewritten. The `app.core.config` to `app.core.agent.config` composition is acyclic (agent.config depends only on pydantic; core.config imports from agent.config in one direction).

One Warning concerns a dependency-declaration gap: `openai_adapter.py` now `import httpx` directly, but `requirements.txt` does not pin `httpx`. It works today only because the `openai>=1.50` package transitively installs it. Three Info items flag a minor unused import, a model-name fallback inconsistency, and a documented `Any` type on `ToolResult.chart`.

## Warnings

### WR-01: httpx imported directly but not declared in requirements.txt

**File:** `app/adapters/llm/openai_adapter.py:12`
**Issue:** After this phase, `openai_adapter.py` imports `httpx` at module top level (`import httpx`) and constructs `httpx.Timeout(30.0)`. `httpx` is currently only a transitive dependency of `openai>=1.50`; it is not listed in `requirements.txt`. This works today but is fragile:
- A future openai SDK release could replace `httpx` with another HTTP client, silently breaking `import httpx`.
- Any consumer running `pip install --no-deps` or auditing direct deps would miss it.
- It violates the project convention that direct imports map to declared dependencies (see `requirements.txt` where `requests`, `pymysql`, etc. are all declared even though they are pulled in transitively by other libs).

**Fix:** Pin `httpx` explicitly in `requirements.txt`, matching the version range the `openai>=1.50` package currently ships with (typically `httpx>=0.27,<1.0`):
```text
# requirements.txt
httpx>=0.27
```
Alternatively, if the team wants to avoid the direct dep, switch `openai_adapter.py` to pass a plain `float`:
```python
_REQUEST_TIMEOUT = 30.0
```
The OpenAI SDK accepts `float`, `httpx.Timeout`, or `None` for `timeout=`. The existing test `RequestTimeoutConstantTest.test_timeout_is_httpx_timeout_30s` would need to be updated to match whichever option is chosen.

## Info

### IN-01: Unused `Iterator` import in test file

**File:** `tests/core/test_app_config_agent.py:8`
**Issue:** `from typing import Iterator` is imported but never referenced anywhere in the file. Linters (ruff/flake8) would flag this as `F401`.
**Fix:** Remove the unused import:
```python
# Delete line 8:
from typing import Iterator
```

### IN-02: Hardcoded `"gpt-4o-mini"` fallback diverges from AgentConfig default

**File:** `app/adapters/llm/openai_adapter.py:55` and `app/adapters/llm/openai_adapter.py:67`
**Issue:** Both `generate_sql` and `stream_text` use `self.config.model or "gpt-4o-mini"` as their model fallback. The new `AgentConfig.model` defaults to `"gpt-4.1-mini"` (per AGENT-09 accuracy escalation note). This creates two different "default model" sources of truth — one for the existing SQL-generation / streaming path on `LLMAdapter`, another for the Phase 2 agent loop. In v1 scope this is not a bug because the agent loop will use `AgentConfig.model` (not `LLMConfig.model`), but operators reading the code may be confused about which default applies when. A comment clarifying the split, or a shared constant, would reduce future confusion.
**Fix:** Either (a) add a short comment above the fallback explaining the split:
```python
# NOTE: This fallback is for the legacy non-agent SQL path.
# The agent loop (Phase 2+) uses AgentConfig.model ("gpt-4.1-mini").
model=self.config.model or "gpt-4o-mini",
```
Or (b) extract a shared `_DEFAULT_LLM_MODEL = "gpt-4o-mini"` module constant so the value is traceable.

### IN-03: `ToolResult.chart: Any | None` defeats static type checking on the chart field

**File:** `app/core/agent/tools/_base.py:27` and `app/core/agent/tools/_base.py:18`
**Issue:** `chart: Any | None` combined with `ConfigDict(arbitrary_types_allowed=True)` is a pragmatic choice to avoid importing plotly at the Tool-protocol layer, but it means type checkers will not catch a tool that stores a non-Figure object in `chart`. The docstring `"plotly.graph_objects.Figure when the tool produced a chart (make_chart only)"` carries the contract informally.
**Fix:** Consider a `TYPE_CHECKING` guard to get static type safety without a runtime import:
```python
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import plotly.graph_objects as go

class ToolResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    ...
    chart: "go.Figure | None" = Field(default=None, ...)
```
This is a low-priority refactor; the current code is correct and the docstring documents the intent. Keeping `Any` is also acceptable for v1.

---

_Reviewed: 2026-04-23T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
