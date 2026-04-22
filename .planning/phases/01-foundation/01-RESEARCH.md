# Phase 1: Foundation — Research

**Researched:** 2026-04-23
**Domain:** Python 3.11 Pydantic 2 contracts, typing.Protocol, OpenAI SDK 1.50+ httpx timeout threading, Streamlit session-state hygiene
**Confidence:** HIGH

## RESEARCH COMPLETE

Phase 1 is a pure-infrastructure contracts phase. The heavy research has already been done in `.planning/research/{SUMMARY,ARCHITECTURE,PITFALLS,STACK}.md` and locked in CONTEXT.md — this document extracts the Phase-1-specific implementation detail so the planner can produce concrete tasks without revisiting upstream ambiguity.

Three technical risks drive Phase 1 design and have explicit mitigations below:
1. **Pydantic 2 mutable-default on `AgentContext._df_cache`** — a `dict`-typed class attribute with a `dict` default would be shared across instances (even though Pydantic deep-copies defaults, we're using a `dataclass`, not a Pydantic model, for `AgentContext`). Mitigation: `field(default_factory=dict)` from `dataclasses`.
2. **`typing.Protocol` without `@runtime_checkable`** can't be used with `isinstance()`. SC3 explicitly requires an isinstance check, so the decorator is required.
3. **`openai.chat.completions.create(timeout=...)` silently dropped in some SDK versions** (historic bug #322, fixed pre-1.0; irrelevant for 1.50+ but documented for context). Per-request `timeout=httpx.Timeout(30.0)` is the current, supported path.

**Primary recommendation:** Four parallel work items in Wave 1 (each file creates independently), followed by a single Wave 2 integration pass (AppConfig composition). Nyquist is disabled per `config.json`, but unit tests are still proposed for SC1–SC4 because they're cheap and provide continuous regression guardrails for Phase 2.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Fixed by Requirements (not negotiable):**
- `AgentConfig` default field values — from REQUIREMENTS.md OBS-03:
  - `max_steps=5`, `row_cap=200`, `timeout_s=30`, `allowed_tables=["ufs_data"]`, `max_context_tokens=30000`, `model="gpt-4.1-mini"`
- `AgentContext` must hold `_df_cache` as an instance-level dict — distinct across instantiations (no shared class-level mutable state).
- `Tool` must be a `typing.Protocol` so any callable matching the signature is structurally compatible — no base-class inheritance required.
- `ToolResult` is a Pydantic model (consistent with existing codebase conventions for multi-value returns; also satisfies `BaseModel.model_json_schema()` usage in TOOL-07 later).
- OpenAI timeout must use `httpx.Timeout(30.0)` and be applied to every `chat.completions.create` call — both `generate_sql` and `stream_text` in `openai_adapter.py`.

**Conventions (follow existing patterns):**
- `from __future__ import annotations` at top of every new module.
- `snake_case` for modules/functions, `PascalCase` for Pydantic models.
- Private names `_`-prefixed (e.g., `_df_cache`).
- Module docstrings in Korean (project language, matches existing files like `config.py`).
- Keyword-only public APIs where applicable.

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase. Use PROJECT.md, REQUIREMENTS.md (AGENT-07, AGENT-08, AGENT-09, OBS-03), and codebase conventions to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
None — Phase 1 scope is narrow and mechanical.

**Adjacent out-of-scope (from ARCHITECTURE + REQUIREMENTS):**
- No tool implementations (Phase 2).
- No loop controller logic (Phase 3).
- No Streamlit UI changes (Phase 4).
- No `TOOL_REGISTRY` assembly — that lands with the first Phase 2 wave.
- No system prompt string — `app/core/agent/prompt.py` is Phase 2/3.
- No `AgentStep` type — that's a Phase 3 loop concern.
- No `validate_and_sanitize` changes — Phase 2 caller-side.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AGENT-07 | Fresh AgentContext per turn; no DataFrame / tool-result / result_N reference survives across turns (stateless per turn). `_df_cache` is instance-level, not class-level. | § AgentContext Shape — `@dataclass` with `_df_cache: dict = field(default_factory=dict)`. Per-turn freshness is enforced by `home.py` constructing a new instance each turn (Phase 4); this phase only guarantees the *shape* supports that contract. |
| AGENT-08 | Every `chat.completions.create` call passes `timeout=httpx.Timeout(30.0)` — applies to BOTH `generate_sql` and `stream_text` in `openai_adapter.py`. | § OpenAI Timeout — per-request `timeout=` kwarg has been supported since openai SDK 1.x; 1.50+ accepts `float` or `httpx.Timeout`. Two call sites identified: `openai_adapter.py:50` (`generate_sql`) and `openai_adapter.py:61` (`stream_text`). |
| AGENT-09 | Primary model is `"gpt-4.1-mini"`; model name is an `AgentConfig` field so operators can swap to `"gpt-4.1"` without code changes. | § AgentConfig Schema — `model: str = "gpt-4.1-mini"` as a top-level field. Orthogonal to existing `LLMConfig.model` (which stays `"gpt-4o-mini"` for the legacy Explorer/Compare path). Agent loop reads `ctx.config.model`, not `llm_adapter.config.model`. |
| OBS-03 | Agent context and budget fields exposed as a single `AgentConfig` Pydantic model on `AppConfig` — editable via `config/settings.yaml` but not via the Settings UI in v1. | § AgentConfig Schema + § AppConfig Composition — `AppConfig.agent: AgentConfig = Field(default_factory=AgentConfig)`; appears under `app.agent:` in YAML; no Settings UI form work required because `settings_page.py` is not touched this phase. |

</phase_requirements>

## Project Constraints (from CLAUDE.md)

Binding directives the planner must honor:

- **No new pip dependencies.** Every capability needed in Phase 1 already exists in `requirements.txt` (Pydantic 2.7+, openai 1.50+, httpx is transitive via openai). Do not add `httpx` to `requirements.txt` explicitly — it's already present as an openai dependency. [VERIFIED: requirements.txt read]
- **Python 3.11** — `typing.Protocol`, `@runtime_checkable`, and dataclass `field(default_factory=...)` are all native. PEP 604 `X | Y` union syntax is allowed. `from __future__ import annotations` is still required per project convention. [VERIFIED: existing code uses both]
- **Korean module docstrings.** Every new module starts with a `"""...."""` Korean docstring (see `app/core/config.py`, `app/adapters/llm/base.py`). [VERIFIED: read both files]
- **Absolute imports from `app.*` package root.** [VERIFIED: CONVENTIONS.md + grep of existing modules]
- **GSD Workflow Enforcement.** All file edits must land through a GSD plan; this phase goes through `/gsd-execute-phase` per project CLAUDE.md.
- **Compatibility guard:** Explorer / Compare / Settings pages must function unchanged after Home is rewritten. Phase 1 does not touch those pages, but the AppConfig change must not break their existing `load_settings()` / `save_settings()` round-trip. [VERIFIED by § AppConfig Composition YAML round-trip analysis below]

## Standard Stack

### Core (no new deps — already in requirements.txt)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pydantic` | `>=2.7` | `AgentConfig`, `ToolResult` BaseModel | Existing codebase convention (`Settings`, `AppConfig`, `DatabaseConfig`, `LLMConfig` all use Pydantic 2). `BaseModel.model_json_schema()` is required for Phase 2 TOOL-07. [VERIFIED: requirements.txt, app/core/config.py] |
| `dataclasses` (stdlib) | Python 3.11 | `AgentContext` | Matches `SafetyResult` pattern in `app/core/sql_safety.py`. Lighter than Pydantic for runtime-only DI containers that never touch YAML. ARCHITECTURE.md Pattern 1 prescribes `@dataclass`. [VERIFIED: ARCHITECTURE.md §Pattern 1] |
| `typing.Protocol` + `runtime_checkable` (stdlib) | Python 3.11 | `Tool` structural type | Allows any callable with matching shape to register as a tool without inheritance. SC3 requires `isinstance()` check, so `@runtime_checkable` is mandatory. [CITED: typing docs — "Protocol classes decorated with runtime_checkable() act as simple-minded runtime protocols that check only the presence of given attributes"] |
| `httpx` | transitive via `openai>=1.50` | `httpx.Timeout(30.0)` constructor | Already installed (openai depends on it). No explicit `requirements.txt` entry needed per SUMMARY.md §Recommended Stack. [VERIFIED: openai 1.50+ always ships with httpx] |
| `openai` | `>=1.50` | `chat.completions.create(..., timeout=...)` per-request override | Per-request `timeout` kwarg accepts `float` or `httpx.Timeout`. Any value >= 1.0 supports it. [CITED: pypi.org/project/openai — "You can configure timeout with a timeout option, which accepts a float or an httpx.Timeout object... You can override per-request using client.with_options(timeout=5.0).chat.completions.create()"] |
| `pandas` | `>=2.2` | `_df_cache: dict[str, pd.DataFrame]` type hint only (no runtime df ops in Phase 1) | Already a hard dependency. Import only for the type annotation. [VERIFIED: requirements.txt] |
| `pytest` | stdlib-adjacent | Unit tests for SC1–SC4 | Nyquist is disabled per `config.json`, but tests are still recommended. `pytest` is not pinned in `requirements.txt` — planner may need a dev-only install or run via `python -m unittest` for SC-verification. See § Open Questions Q1. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `@dataclass` for `AgentContext` | `pydantic.BaseModel` | Would enable `.model_dump()` for trace logging, but: (a) ARCHITECTURE.md explicitly prescribes dataclass; (b) `pd.DataFrame` is not a Pydantic-native type and would need `arbitrary_types_allowed=True`; (c) the context is runtime-only, never YAML-serialized. **Stick with dataclass.** |
| `typing.Protocol` for `Tool` | `abc.ABC` base class | Inheritance couples all tools to a shared base (matches DB/LLM adapter pattern but is heavier). CONTEXT.md locks Protocol; existing `DBAdapter`/`LLMAdapter` use `ABC` but tools are function-shaped and stateless, so Protocol is a better fit. **Protocol per CONTEXT.md.** |
| `dict` for `ToolResult` | `pydantic.BaseModel` | Dict lacks schema introspection for TOOL-07. **Pydantic per CONTEXT.md.** |
| `float` timeout | `httpx.Timeout(30.0)` | Bare float works, but SUMMARY.md §Key Findings and CONTEXT.md both specify `httpx.Timeout(30.0)`. Using the object form also leaves room to specify connect/read/write separately later (e.g., longer read for streaming) without a breaking API change. **httpx.Timeout per CONTEXT.md.** |
| `"gpt-4o-mini"` default | `"gpt-4.1-mini"` | AGENT-09 explicitly names `gpt-4.1-mini`. SUMMARY.md §Recommended Stack confirms: "~$0.40/$1.60 per 1M tokens, ~$0.004 per 5-step loop, tool-call reliability stronger than gpt-4o, deprecates 2026-11-04". **`gpt-4.1-mini` per AGENT-09.** |

**Installation:**

No new installation required. Verify with:

```bash
pip show pydantic openai httpx 2>/dev/null | grep -E "Name|Version"
```

**Version verification (on the target machine — done 2026-04-23):**

Python packages are not currently importable on the GSD working shell (no venv activated), so runtime versions cannot be confirmed here. The lockfile `requirements.txt` pins `pydantic>=2.7`, `openai>=1.50`. Planner should add a first-task verification step:

```bash
python -c "import pydantic, openai, httpx; print(pydantic.__version__, openai.__version__, httpx.__version__)"
```

…as a precondition check before the Wave 1 implementation tasks begin. [VERIFIED: requirements.txt pins]

## Architecture Patterns

### Recommended Project Structure

```
app/
└── core/
    ├── agent/                        # NEW package
    │   ├── __init__.py               # NEW — empty package marker
    │   ├── config.py                 # NEW — AgentConfig Pydantic model
    │   ├── context.py                # NEW — AgentContext dataclass
    │   └── tools/                    # NEW sub-package
    │       ├── __init__.py           # NEW — empty for now (Phase 2 fills with TOOL_REGISTRY)
    │       └── _base.py              # NEW — Tool Protocol + ToolResult model
    ├── config.py                     # MODIFY — append `agent: AgentConfig` to AppConfig
    └── session.py                    # AUDIT only — no changes this phase

app/adapters/llm/
└── openai_adapter.py                 # MODIFY — add httpx import + timeout kwarg on 2 call sites

tests/                                # NEW directory (absent today)
└── core/
    └── agent/
        ├── __init__.py               # NEW
        ├── test_config.py            # NEW — SC1 verification
        ├── test_context.py           # NEW — SC2 verification
        ├── test_tools_base.py        # NEW — SC3 verification
        └── test_openai_timeout.py    # NEW — SC4 verification
```

**Rationale for flat `tests/` mirror:** The codebase has no existing `tests/` directory [VERIFIED: `ls tests/` returned "No such file or directory"]. Per pytest convention, `tests/` is the standard location. Mirror the `app/` structure for import clarity.

### Pattern 1: AgentConfig — Nested Pydantic Model on AppConfig

```python
# app/core/agent/config.py
"""에이전트 실행 컨텍스트 및 예산 설정."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """에이전트 루프 예산 및 모델 설정.

    YAML 경로: settings.yaml → app.agent.*
    v1에서는 Settings UI에서 편집하지 않고 YAML 파일 직접 편집만 허용한다.
    """
    model: str = Field(
        default="gpt-4.1-mini",
        description="OpenAI tool-capable model. Swap to 'gpt-4.1' for accuracy escalation.",
    )
    max_steps: int = Field(default=5, ge=1, le=20)
    row_cap: int = Field(default=200, ge=1, le=10000)
    timeout_s: int = Field(default=30, ge=5, le=300)
    allowed_tables: list[str] = Field(default_factory=lambda: ["ufs_data"])
    max_context_tokens: int = Field(default=30_000, ge=1000, le=1_000_000)
```

**Why this shape:**
- `ge`/`le` bounds prevent operators from mis-configuring (e.g., `max_steps=0` would dead-loop, `timeout_s=1` would never complete a streaming call). Bounds are wide enough to allow real-world tuning. [CITED: REQUIREMENTS.md OBS-03 budget fields]
- `default_factory=lambda: ["ufs_data"]` — Pydantic 2 deep-copies `default` lists safely, but CONVENTIONS.md best-practice (and `Field(default_factory=list)` elsewhere in `app/core/config.py:38, 49`) is `default_factory`. Also protects against a future change where a reader mutates the list. [CITED: "Pydantic handles mutable defaults correctly by creating a deep copy for every model instance... default_factory is still the recommended approach, because it's explicit and semantically correct"]
- `model` is a plain `str`, not `Literal["gpt-4.1-mini", "gpt-4.1"]` — AGENT-09 requires operator-swappable without code changes, so a literal type would block that. A `description=` Field hint guides the operator. [CITED: AGENT-09 "operators can swap to 'gpt-4.1' without code changes"]
- No `ConfigDict(frozen=True)` — operators may want to mutate at runtime for experimentation (Phase 4/5 follow-on). CONTEXT.md doesn't lock frozen/non-frozen; default (mutable) matches `AppConfig` elsewhere.

### Pattern 2: AgentContext — Dataclass with Instance-Level `_df_cache`

```python
# app/core/agent/context.py
"""에이전트 턴 단위 실행 컨텍스트 (DI 컨테이너).

home.py가 매 턴마다 새로 구성하고 run_agent_turn()에 주입한다.
_df_cache는 인스턴스 속성이므로 턴 간 공유되지 않는다(AGENT-07 stateless-per-turn).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.adapters.db.base import DBAdapter
from app.adapters.llm.base import LLMAdapter
from app.core.agent.config import AgentConfig


@dataclass
class AgentContext:
    db_adapter: DBAdapter
    llm_adapter: LLMAdapter
    db_name: str
    user: str
    config: AgentConfig
    _df_cache: dict[str, pd.DataFrame] = field(default_factory=dict)

    def store_df(self, tool_call_id: str, df: pd.DataFrame) -> None:
        self._df_cache[tool_call_id] = df

    def get_df(self, tool_call_id: str) -> pd.DataFrame | None:
        return self._df_cache.get(tool_call_id)
```

**Why this shape:**
- `field(default_factory=dict)` — the **critical** detail for AGENT-07. A bare `_df_cache: dict[str, pd.DataFrame] = {}` would be a class-level mutable default shared across instances. Dataclass catches this at decoration time and raises `ValueError`, but the canonical fix is `default_factory`. [CITED: Python dataclasses docs — mutable default handling]
- `store_df` / `get_df` helpers match ARCHITECTURE.md §Pattern 1 verbatim; Phase 2 `pivot_to_wide` and `make_chart` rely on them.
- **No token-tracking, step-counter, or trace-log fields** per CONTEXT.md §Specific Ideas: "Keep AgentContext lean. Only `_df_cache` is required by AGENT-07 + TOOL-03/TOOL-04 downstream. Do not pre-add fields for 'future' memory / token tracking — AGENT-06's token accounting lives in the loop (Phase 3), not the context."
- `llm_adapter: LLMAdapter` — typed against the abstract base (not `OpenAIAdapter`). Phase 3's loop does one `isinstance(ctx.llm_adapter, OpenAIAdapter)` check at entry per ARCHITECTURE.md §Adapter Pattern Preservation; tools only see the abstract interface.

### Pattern 3: Tool Protocol + ToolResult — Structural Typing

```python
# app/core/agent/tools/_base.py
"""Tool 프로토콜 및 ToolResult 모델.

모든 Phase 2 도구는 Tool 프로토콜을 구조적으로 만족해야 한다(상속 불필요).
ToolResult는 BaseModel이므로 model_json_schema()를 통해 TOOL-07 스키마 생성에 재사용된다.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from app.core.agent.context import AgentContext


class ToolResult(BaseModel):
    """도구 실행 결과. 모델에 전달되는 문자열 + 선택적 구조화 페이로드."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    content: str = Field(description="Text returned to the model as the tool response.")
    df_ref: str | None = Field(
        default=None,
        description="AgentContext._df_cache key when a DataFrame was stored.",
    )
    chart: Any | None = Field(
        default=None,
        description="plotly.graph_objects.Figure when the tool produced a chart (make_chart only).",
    )


@runtime_checkable
class Tool(Protocol):
    """도구는 name, args_model, __call__ 세 속성을 갖는 구조적 타입.

    args_model은 Pydantic BaseModel의 서브클래스이며 OpenAI 도구 스키마
    생성(TOOL-07)의 단일 진실 소스가 된다.
    """

    name: str

    @property
    def args_model(self) -> type[BaseModel]: ...

    def __call__(self, ctx: AgentContext, args: BaseModel) -> ToolResult: ...
```

**Why this shape:**

- `@runtime_checkable` is **mandatory** for SC3's `isinstance()` check. Without it, `isinstance(obj, Tool)` raises `TypeError`. [CITED: typing docs — "Protocol classes without this decorator cannot be used as the second argument to isinstance() or issubclass()"]
- **`args_model` as a Pydantic `BaseModel` subclass (not an instance)** enables `tool.args_model.model_json_schema()` for Phase 2 TOOL-07 without constructing a placeholder instance. This shape mirrors how `openai-python` tool examples expose schemas.
- **`ToolResult` fields are a superset of CONTEXT.md's "content: str" requirement.** The research summary says ToolResult needs room for structured payloads (chart, df_ref). Two safe alternatives were considered:
  - **Discriminated union** (`ToolResultText | ToolResultChart | ToolResultDfRef`) — more type-safe but forces each tool to pick one variant and blocks mixed results (e.g., `make_chart` returns both `content` summary AND `chart` figure). Rejected.
  - **Single model, Optional fields** (chosen) — `content` is always required; `df_ref` and `chart` are `None` unless the tool produced them. Simpler, matches ARCHITECTURE.md §Pattern 2 where `ToolResult` has `content`, `df`, `chart` as a flat dataclass. We upgrade `df` to `df_ref: str | None` (a cache key) because the DataFrame itself lives in `AgentContext._df_cache`; only the key needs to cross the loop boundary back to the model.
- `arbitrary_types_allowed=True` lets `chart: Any` hold a `plotly.graph_objects.Figure` (not Pydantic-native). The `df_ref` change removes the need for a `pd.DataFrame` field, which would otherwise require the same config flag for that reason.
- `args: BaseModel` (not `**kwargs`) — after JSON argument parsing in Phase 3's loop, the loop validates the args dict through `tool.args_model.model_validate(args_dict)` and passes the validated instance to `tool(ctx, args)`. This centralizes validation and matches TOOL-07.

**Note on divergence from ARCHITECTURE.md § Pattern 2:** ARCHITECTURE.md sketched `def __call__(self, ctx: AgentContext, **kwargs) -> ToolResult` and `schema: dict` (hand-authored). CONTEXT.md §Fixed by Requirements overrides this: "ToolResult is a Pydantic model... `BaseModel.model_json_schema()` usage in TOOL-07 later." This implies the Pydantic args_model approach, not hand-authored dict schemas. The planner should expect Phase 2 tools to follow the `args_model` shape. If a phase-level decision later flips back to hand-authored dicts, the `_base.py` Protocol can be revised with a small refactor (change `args_model` → `schema: dict` and call sites update accordingly).

### Pattern 4: AppConfig Composition (YAML Round-Trip Safety)

```python
# app/core/config.py — MODIFIED
from app.core.agent.config import AgentConfig  # NEW import

class AppConfig(BaseModel):
    default_database: str = ""
    default_llm: str = ""
    query_row_limit: int = 1000
    recent_query_history: int = 20
    agent: AgentConfig = Field(default_factory=AgentConfig)  # NEW
```

**YAML round-trip analysis:**

- `load_settings()` reads YAML via `yaml.safe_load` → `Settings.model_validate(data)` [VERIFIED: app/core/config.py:59-65].
- **Old settings.yaml (without `app.agent:` key):** Pydantic 2 nested model defaults are applied when the key is absent — `AppConfig(default_database="...", ...).agent` falls back to `AgentConfig()` with all defaults. No error, no migration script required. [CITED: Pydantic 2 docs — "default" and "default_factory" on nested models are applied when the key is missing]
- **Pydantic 2 `extra` handling:** Default is `"ignore"` (not `"forbid"`). Unknown YAML keys won't break validation, so if a future phase adds more `agent.*` fields, old YAMLs still load. [CITED: Pydantic 2 docs — "the default being 'ignore'"]
- **`save_settings()` writes via `settings.model_dump(mode='python')` + `yaml.safe_dump`** [VERIFIED: app/core/config.py:68-77]. After this phase, saved YAML will include a new `app.agent:` block with all defaults. **This is a behavior change visible to operators who re-save via Settings UI** — the YAML grows a new section. Verify it's valid YAML by running `yaml.safe_load(yaml.safe_dump(Settings().model_dump(mode='python')))` in a test.
- **No changes to `settings_page.py` required** this phase — OBS-03 explicitly says "not via the Settings UI in v1". The form generation in settings_page.py iterates over DatabaseConfig / LLMConfig fields only; AgentConfig is nested under `app` and the existing form does not auto-reflect it. The operator edits `config/settings.yaml` directly.

**Example post-Phase-1 YAML fragment:**

```yaml
app:
  default_database: "Production MySQL (Read-only)"
  default_llm: "GPT-4o Mini"
  query_row_limit: 1000
  recent_query_history: 20
  agent:
    model: "gpt-4.1-mini"
    max_steps: 5
    row_cap: 200
    timeout_s: 30
    allowed_tables:
      - "ufs_data"
    max_context_tokens: 30000
```

### Pattern 5: OpenAI httpx Timeout — Both Call Sites

```python
# app/adapters/llm/openai_adapter.py — MODIFIED
"""OpenAI LLM 어댑터.

openai>=1.0 SDK의 chat.completions API 사용.
API key는 설정에 직접 입력하거나, 비워두면 OPENAI_API_KEY 환경변수를 사용한다.
30초 요청 타임아웃(httpx.Timeout)으로 무한 대기를 방지한다 (AGENT-08).
"""
from __future__ import annotations

import os
from typing import Iterable

import httpx                             # NEW import
from openai import OpenAI

from app.adapters.llm.base import LLMAdapter, SQL_SYSTEM_PROMPT

_REQUEST_TIMEOUT = httpx.Timeout(30.0)   # NEW module constant


class OpenAIAdapter(LLMAdapter):
    # ... unchanged helper methods ...

    def generate_sql(self, question, schema_summary, history=None):
        # ... unchanged messages build ...
        resp = client.chat.completions.create(
            model=self.config.model or "gpt-4o-mini",
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            extra_headers=self._extra_headers(),
            timeout=_REQUEST_TIMEOUT,       # NEW
        )
        return (resp.choices[0].message.content or "").strip()

    def stream_text(self, prompt):
        # ... unchanged ...
        stream = client.chat.completions.create(
            model=self.config.model or "gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=True,
            extra_headers=self._extra_headers(),
            timeout=_REQUEST_TIMEOUT,       # NEW
        )
        # ...
```

**Why this shape:**
- Module-level constant `_REQUEST_TIMEOUT` (prefixed `_` per CONVENTIONS.md §Naming: "Private module-level constants use `_UPPERCASE`") ensures both call sites use the same value and makes the grep in SC4 trivial: `grep -c '_REQUEST_TIMEOUT' app/adapters/llm/openai_adapter.py` ≥ 3 (definition + 2 usages).
- Alternative (inline `timeout=httpx.Timeout(30.0)` twice) also satisfies SC4's grep: `grep -c 'httpx.Timeout(30.0)' ...` ≥ 2. Either is acceptable; the constant form is DRY and testable (a unit test can `from openai_adapter import _REQUEST_TIMEOUT; assert _REQUEST_TIMEOUT.connect is None and _REQUEST_TIMEOUT.read == 30.0`). **Recommend the constant form.**
- Korean docstring is extended with a new line "30초 요청 타임아웃(httpx.Timeout)으로 무한 대기를 방지한다 (AGENT-08)." per CLAUDE.md convention.
- **Do NOT move the timeout onto the `OpenAI()` client constructor.** A client-level default would also affect streaming reads (typically longer). Per-request `timeout=` lets each call declare its own window; keeps 30s for the non-streaming agent loop turn and leaves room for a different timeout if Phase 3 needs it. [CITED: openai docs — "You can configure the default for all requests ... or use more granular control ... override per-request"]
- **Why `httpx.Timeout(30.0)` instead of a bare `30.0` float:** CONTEXT.md locks this. `httpx.Timeout(30.0)` with a single positional arg sets `connect`, `read`, `write`, and `pool` all to 30s — equivalent to the float form today but more explicit. If Phase 3 ever needs to set `read=60.0` separately (for streaming), the object form is already in place.

### Anti-Patterns to Avoid

- **Class-level mutable dict default on `AgentContext`.** `_df_cache: dict = {}` would either raise `ValueError` at decoration time (dataclass) or be shared across instances (plain class). Always `field(default_factory=dict)`.
- **`Protocol` without `@runtime_checkable`.** SC3 requires `isinstance()`. Forgetting the decorator gives `TypeError: Instance and class checks can only be used with @runtime_checkable protocols`.
- **Hard-coding `"gpt-4.1-mini"` inside `openai_adapter.py`.** The adapter's `self.config.model` continues to serve the legacy Explorer/Compare NL→SQL flow with `"gpt-4o-mini"`. The agent loop in Phase 3 will read `ctx.config.model` (i.e., `AgentConfig.model`) instead; the two paths are deliberately orthogonal.
- **Over-eager Pydantic conversion of `AgentContext`.** Tempting because `AgentConfig` is Pydantic, but dataclass is simpler for a per-turn DI container holding a `pd.DataFrame` cache. Converting to Pydantic requires `arbitrary_types_allowed=True` and adds model validation overhead per turn construction (5+ per page interaction).
- **Silent removal of `pending_sql` session-state key in this phase.** Phase 4 owns the Home rewrite and the HOME-02 deletion. Phase 1 only audits — do not touch `home.py`.
- **Prefix without version suffix on new agent session-state key.** The canonical new key is `_AGENT_TRACE_KEY = "agent_trace_v1"` — `_v1` suffix future-proofs against key shape changes in v2 (when cross-turn memory / MEM-01 arrives). This matches the pattern in existing projects but is a Phase 4 concern; Phase 1 only documents the recommendation.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Config file parsing + validation | Custom YAML-to-dataclass code | `pydantic.BaseModel` + existing `load_settings()`/`save_settings()` in `app/core/config.py` | Already works; nested model defaults are applied automatically when YAML keys are absent. [VERIFIED] |
| Structural tool typing | Custom registration metaclass or decorator | `typing.Protocol` + `@runtime_checkable` | Stdlib since Python 3.8; zero dependencies. [CITED: PEP 544] |
| HTTP timeout enforcement | `threading.Timer` / `signal.alarm` wrapping OpenAI calls | OpenAI SDK's built-in `timeout=httpx.Timeout(30.0)` per-request kwarg | Native to openai>=1.0; handles connect/read/write separately; raises `openai.APITimeoutError`. [CITED: openai-python README] |
| Instance-level cache init | Manual `__post_init__` with `self._df_cache = {}` | `field(default_factory=dict)` in dataclass | One line, stdlib, impossible to get wrong. [CITED: dataclasses docs] |
| Session-state key collision detection | Runtime introspection of `st.session_state.keys()` | A single `_AGENT_TRACE_KEY = "agent_trace_v1"` naming convention + grep audit | The existing session.py pattern uses private-prefixed constants; Streamlit session_state is a dict, so predictable keys win. |

**Key insight:** Phase 1 is a "discover + wire existing primitives" phase, not an invention phase. Every primitive (Pydantic nested model, dataclass default_factory, typing.Protocol, httpx.Timeout) is stdlib or already-pinned. Hand-rolling any of the above would add bugs.

## Runtime State Inventory

Phase 1 is a contracts / new-module phase, not a rename or migration. This section is included for completeness with explicit "nothing to migrate" findings per category, because Phase 1 touches one existing module (`openai_adapter.py`) and one shared model (`AppConfig`).

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | **None.** No DB tables, caches, or persistent stores hold any Phase 1 symbol names. `ufs_data` is referenced in `AgentConfig.allowed_tables` default but is pre-existing MySQL schema (the whole project target). | None |
| Live service config | **None.** No external services configure anything we touch here. | None |
| OS-registered state | **None.** No systemd / pm2 / launchd / Windows Task Scheduler artifacts reference agent module paths. | None |
| Secrets/env vars | `OPENAI_API_KEY` is read by `openai_adapter.py` — unchanged by Phase 1 (we add a timeout kwarg, not auth). `SETTINGS_PATH` override continues to work with the new `app.agent:` YAML block. | None |
| Build artifacts | **Python bytecode only.** First run after `openai_adapter.py` modification invalidates `__pycache__/*.pyc` — Python regenerates on import. Docker image rebuilds are not required since no new pip deps are added. | None — no manual cleanup |

**The canonical question:** *After every file in the repo is updated, what runtime systems still have the old string cached, stored, or registered?*

**Answer:** None. Phase 1 introduces new module paths (`app.core.agent.*`) that no runtime system could reference yet. The one existing file modification (`openai_adapter.py` timeout) is purely additive — no old call signature to migrate. The one existing model modification (`AppConfig.agent` field) is backward-compatible via Pydantic nested defaults.

## Common Pitfalls

### Pitfall 1: Class-level dict default on AgentContext

**What goes wrong:** `_df_cache: dict[str, pd.DataFrame] = {}` on a dataclass raises `ValueError: mutable default <class 'dict'> for field _df_cache is not allowed: use default_factory`. On a plain class it silently shares the dict across all instances.

**Why it happens:** Python's function/class-level mutable defaults are evaluated once at class-body execution time. Dataclass catches the common cases (`list`, `dict`, `set`); a plain class does not.

**How to avoid:** Always `field(default_factory=dict)`. Unit test asserts two fresh `AgentContext` instances have independent `_df_cache` identity — `ctx1._df_cache is not ctx2._df_cache`.

**Warning signs:** A failing SC2 test, OR a Phase 4 bug where one user's chart references another user's DataFrame (would only manifest with a multi-worker Streamlit deployment, which is out of scope, but the test catches it regardless).

### Pitfall 2: Forgetting `@runtime_checkable` on `Tool`

**What goes wrong:** `isinstance(some_tool, Tool)` raises `TypeError: Instance and class checks can only be used with @runtime_checkable protocols`.

**Why it happens:** `typing.Protocol` default is type-check-only; `@runtime_checkable` is opt-in for `isinstance` support.

**How to avoid:** Decorator on `Tool` class. SC3 test explicitly calls `isinstance(ToyTool(), Tool)` to catch this at CI time.

**Warning signs:** Phase 2 `TOOL_REGISTRY` assembly test fails with TypeError when validating registered tools.

### Pitfall 3: OpenAI timeout dropped by wrapper layer

**What goes wrong:** Historical issue #322 in openai-python: `Chat.create` removed `timeout` from kwargs. Fixed pre-1.0; current SDK preserves it.

**Why it happens (historically):** Old kwargs filtering in the client wrapper.

**How to avoid:** Pinned `openai>=1.50` in `requirements.txt` — safe. Additional safety: SC4 unit test mocks the OpenAI client and asserts `timeout=httpx.Timeout(30.0)` appears in `create.call_args.kwargs` on every call.

**Warning signs:** Production hang when OpenAI API is slow (>30s); `logs/llm.log` shows calls that never complete. The unit test prevents this from reaching production.

### Pitfall 4: Pydantic 2 `default_factory=lambda: ["ufs_data"]` confused with shared reference

**What goes wrong:** Developer mistakenly writes `default=["ufs_data"]` thinking it's equivalent. It is, in Pydantic 2, because Pydantic deep-copies the default — but this is a fragile contract and looks suspicious in code review.

**Why it happens:** Confusion with plain Python function defaults, where `def f(x=[]): ...` is the classic gotcha.

**How to avoid:** Always `Field(default_factory=lambda: ["ufs_data"])` per CONVENTIONS.md and existing `app/core/config.py:38` pattern. Fails no test, but reads better and survives a future Pydantic version that might not deep-copy. [CITED: Pydantic docs — "Despite Pydantic's internal safety mechanisms, using default_factory=list is still the recommended approach"]

**Warning signs:** Code review comment; not a runtime bug in Pydantic 2.7+.

### Pitfall 5: AppConfig YAML round-trip breaks existing settings.yaml

**What goes wrong:** User already has `config/settings.yaml` without an `app.agent:` block. Loading produces a validation error.

**Why it happens:** Only if `AgentConfig` had required fields (no defaults). It doesn't — all fields have defaults — so `Settings.model_validate({})` succeeds, and so does loading an old settings.yaml.

**How to avoid:** Verified by a round-trip test: write an old settings.yaml fragment to a temp path, `load_settings()` succeeds, `.app.agent.max_steps == 5`. Planner should include this as a precondition test in the AppConfig composition task.

**Warning signs:** Test fails; operator reports "app won't start after Phase 1 pull."

### Pitfall 6: Session-state key collision during Phase 4 swap

**What goes wrong:** Phase 4 deletes `pending_sql` references in `home.py` but an operator with a pre-Phase-4 browser tab open still has `st.session_state["pending_sql"] = "SELECT..."` cached. After deploy, new home.py ignores it silently (no code path reads it) — no bug. But if Phase 4 accidentally names a new key `pending_sql` with different meaning, a stale string from old session causes a type error or wrong behavior.

**Why it happens:** Streamlit session_state persists across page reloads within the same tab/session.

**How to avoid:** Phase 1 audits and **documents** the legacy keys. Phase 4 uses a distinct prefix (`_AGENT_TRACE_KEY = "agent_trace_v1"`). Do NOT reuse `pending_sql`, `pending_sql_edit`, `cmp_a`, `cmp_b`, `explorer_df` for new purposes.

**Warning signs:** Existing keys collide with new agent keys — detected by SC5 audit.

## Session-State Audit

Canonical list of all `st.session_state` keys in use today [VERIFIED: grep of `app/`]:

| Key | Defined in | Purpose | Phase 1 Action | Phase 4 Action |
|-----|------------|---------|----------------|----------------|
| `chat_history` | `app/core/session.py:9` (`_CHAT_HISTORY_KEY`) | Chat turns (user + assistant messages) | **Keep** — will hold `append_chat("user", q)` + `append_chat("assistant", final_text)` in agent era | None (reused by HOME-04) |
| `recent_queries` | `app/core/session.py:10` (`_RECENT_QUERIES_KEY`) | Recent SQL executions for the sidebar "최근 질의" panel | **Keep** — `record_recent_query()` still called from agent path | None (preserved by HOME-03) |
| `selected_db` | `app/core/session.py:11` (`_SELECTED_DB_KEY`) | Currently selected DB name (sidebar) | **Keep** — resolved by `resolve_selected_db()` | None |
| `selected_llm` | `app/core/session.py:12` (`_SELECTED_LLM_KEY`) | Currently selected LLM name (sidebar) | **Keep** — resolved by `resolve_selected_llm()` | None |
| `user` | `app/core/auth.py` (via `streamlit_authenticator`) | Authenticated username — read for log attribution | **Keep** | None |
| `pending_sql` | `app/pages/home.py:102, 104, 140, 150` | Old flow: LLM-generated SQL awaiting user confirmation | **Audit only — document for Phase 4 removal.** No code read/write this phase. | **Remove** (HOME-02) |
| `pending_sql_edit` | `app/pages/home.py:111` | `st.text_area` widget key for SQL edit | **Audit only — document for Phase 4 removal.** Orphans cleanly when the text_area is deleted. | **Remove** (HOME-02) |
| `cmp_a`, `cmp_b` | `app/pages/compare.py:68-69, 71-72` | Comparison page DataFrame buffers | **Keep** — Compare page unchanged per HOME-05 | None |
| `explorer_df` | `app/pages/explorer.py:72-73, 84, 106` | Explorer page DataFrame buffer | **Keep** — Explorer page unchanged per HOME-05 | None |

**Legacy Home keys to earmark for Phase 4 removal:** `pending_sql`, `pending_sql_edit`.

**Recommended new agent-era key convention (for Phase 4 to adopt):**

```python
# app/core/session.py — Phase 4 adds these; Phase 1 only documents
_AGENT_TRACE_KEY = "agent_trace_v1"   # list of AgentStep events for the current turn's trace expander
```

The `_v1` suffix future-proofs against shape changes in v2 (MEM-01 cross-turn memory). No other agent-era keys are expected in v1 — the DataFrame cache lives on `AgentContext._df_cache`, not session state, per AGENT-07.

**No Phase 1 code change** to `session.py` — audit + documented recommendation is the deliverable. The Phase 4 planner inherits this table.

**Grep commands for verification (SC5):**

```bash
# What keys exist today
grep -rhE "st\.session_state(\[\"[^\"]+\"\]|\._[a-z_]+|\.[a-z_]+)" app/ | sort -u

# Verify no Phase 1 code accidentally adds agent-era keys
grep -rn "agent_trace\|pending_sql" app/core/agent/ 2>/dev/null   # Expect: no matches

# Verify existing legacy keys are untouched by Phase 1
grep -rn "pending_sql" app/pages/home.py | wc -l                   # Expect: 7 (unchanged from audit)
```

## Code Examples

### SC1: AgentConfig unit test

```python
# tests/core/agent/test_config.py
"""AgentConfig 필드 기본값 및 YAML 라운드트립 검증 (SC1)."""
from __future__ import annotations

import yaml

from app.core.agent.config import AgentConfig
from app.core.config import Settings, save_settings, load_settings


def test_agent_config_defaults() -> None:
    c = AgentConfig()
    assert c.model == "gpt-4.1-mini"
    assert c.max_steps == 5
    assert c.row_cap == 200
    assert c.timeout_s == 30
    assert c.allowed_tables == ["ufs_data"]
    assert c.max_context_tokens == 30_000


def test_agent_config_serializable() -> None:
    c = AgentConfig()
    dumped = c.model_dump()
    assert dumped == {
        "model": "gpt-4.1-mini",
        "max_steps": 5,
        "row_cap": 200,
        "timeout_s": 30,
        "allowed_tables": ["ufs_data"],
        "max_context_tokens": 30_000,
    }
    # Round-trip via YAML
    text = yaml.safe_dump(dumped)
    assert AgentConfig.model_validate(yaml.safe_load(text)) == c


def test_agent_config_bounds() -> None:
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        AgentConfig(max_steps=0)
    with pytest.raises(ValidationError):
        AgentConfig(timeout_s=2)


def test_allowed_tables_is_instance_level(tmp_path, monkeypatch) -> None:
    """Two AgentConfig instances have independent allowed_tables lists."""
    c1 = AgentConfig()
    c2 = AgentConfig()
    c1.allowed_tables.append("other_table")
    assert c2.allowed_tables == ["ufs_data"]   # Pydantic deep-copies default_factory output
```

### SC2: AgentContext unit test

```python
# tests/core/agent/test_context.py
"""AgentContext _df_cache 인스턴스별 독립성 검증 (SC2, AGENT-07)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from app.core.agent.config import AgentConfig
from app.core.agent.context import AgentContext


def _mk() -> AgentContext:
    return AgentContext(
        db_adapter=MagicMock(),
        llm_adapter=MagicMock(),
        db_name="test",
        user="alice",
        config=AgentConfig(),
    )


def test_df_cache_is_instance_level() -> None:
    ctx1 = _mk()
    ctx2 = _mk()
    ctx1.store_df("call_1", pd.DataFrame({"x": [1]}))
    assert ctx2.get_df("call_1") is None
    assert ctx1._df_cache is not ctx2._df_cache


def test_store_and_get_df() -> None:
    ctx = _mk()
    df = pd.DataFrame({"y": [42]})
    ctx.store_df("call_abc", df)
    assert ctx.get_df("call_abc") is df
    assert ctx.get_df("missing") is None
```

### SC3: Tool Protocol unit test

```python
# tests/core/agent/test_tools_base.py
"""Tool Protocol 구조적 타입 검증 (SC3)."""
from __future__ import annotations

from unittest.mock import MagicMock

from pydantic import BaseModel

from app.core.agent.config import AgentConfig
from app.core.agent.context import AgentContext
from app.core.agent.tools._base import Tool, ToolResult


class _ToyArgs(BaseModel):
    message: str


class _ToyTool:
    name = "toy"
    args_model = _ToyArgs

    def __call__(self, ctx: AgentContext, args: BaseModel) -> ToolResult:
        return ToolResult(content=f"echo: {args.message}")


def test_toy_tool_satisfies_protocol() -> None:
    t = _ToyTool()
    assert isinstance(t, Tool)


def test_non_tool_fails_protocol() -> None:
    # Object missing `name` attribute
    class _NotATool:
        args_model = _ToyArgs
        def __call__(self, ctx, args): ...
    assert not isinstance(_NotATool(), Tool)


def test_tool_result_serializable() -> None:
    r = ToolResult(content="hello")
    assert r.model_dump()["content"] == "hello"
    assert r.df_ref is None
    assert r.chart is None


def test_tool_result_full() -> None:
    r = ToolResult(content="42 rows", df_ref="call_xyz", chart=None)
    assert r.df_ref == "call_xyz"


def test_tool_call_returns_tool_result() -> None:
    ctx = AgentContext(
        db_adapter=MagicMock(),
        llm_adapter=MagicMock(),
        db_name="db",
        user="u",
        config=AgentConfig(),
    )
    t = _ToyTool()
    result = t(ctx, _ToyArgs(message="hi"))
    assert isinstance(result, ToolResult)
    assert result.content == "echo: hi"
```

### SC4: OpenAI timeout unit test

```python
# tests/core/agent/test_openai_timeout.py
"""openai_adapter.py chat.completions.create 타임아웃 검증 (SC4, AGENT-08)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from app.adapters.llm.openai_adapter import OpenAIAdapter, _REQUEST_TIMEOUT
from app.core.config import LLMConfig


def _mk_adapter() -> OpenAIAdapter:
    cfg = LLMConfig(name="t", type="openai", model="gpt-4o-mini", api_key="sk-test")
    return OpenAIAdapter(cfg)


def test_request_timeout_constant() -> None:
    """Module-level constant is httpx.Timeout(30.0)."""
    assert isinstance(_REQUEST_TIMEOUT, httpx.Timeout)
    # httpx.Timeout(30.0) sets all phases to 30s
    assert _REQUEST_TIMEOUT.read == 30.0


def test_generate_sql_passes_timeout() -> None:
    a = _mk_adapter()
    with patch.object(a, "_client") as mock_client_fn:
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="SELECT 1"))]
        )
        mock_client_fn.return_value = fake_client
        a.generate_sql(question="q", schema_summary="")
        kwargs = fake_client.chat.completions.create.call_args.kwargs
        assert kwargs["timeout"] is _REQUEST_TIMEOUT


def test_stream_text_passes_timeout() -> None:
    a = _mk_adapter()
    with patch.object(a, "_client") as mock_client_fn:
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = iter([])   # empty stream
        mock_client_fn.return_value = fake_client
        list(a.stream_text("prompt"))
        kwargs = fake_client.chat.completions.create.call_args.kwargs
        assert kwargs["timeout"] is _REQUEST_TIMEOUT
        assert kwargs["stream"] is True
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Class-body `schema: dict = {...}` hand-authored per tool | `args_model: type[BaseModel]` per tool + `model_json_schema()` for the OpenAI wire format | CONTEXT.md decision (2026-04-23) overrides ARCHITECTURE.md Pattern 2 to unlock TOOL-07 single-source-of-truth | Phase 2 tools author one Pydantic model, not two artifacts (Python signature + JSON schema dict). [CITED: CONTEXT.md Fixed by Requirements] |
| `timeout=30.0` (bare float) | `timeout=httpx.Timeout(30.0)` | SUMMARY.md §Recommended Stack + CONTEXT.md (2026-04-22/23) | Future-ready for per-phase timeout tuning (e.g., longer `read` for streaming) without API change |
| `gpt-4o-mini` | `gpt-4.1-mini` | AGENT-09 (2026-04-22) | Better tool-call reliability, 1M context, lower per-token cost. Deprecates 2026-11-04 — successor pin is a v2 HARD-05 concern. |
| `AgentContext` fields for token tracking | Token tracking lives in `loop.py` (Phase 3), context stays lean | CONTEXT.md §Specific Ideas | Keeps Phase 1 minimal; no speculative fields |

**Deprecated/outdated:**
- ARCHITECTURE.md Pattern 2's hand-authored `schema: dict` — superseded by CONTEXT.md's Pydantic `args_model` approach. Planner should note the divergence and use the CONTEXT.md direction.
- Old Home flow session keys (`pending_sql`, `pending_sql_edit`) — earmarked for Phase 4 removal per HOME-02. Phase 1 leaves them in place.

## Environment Availability

Phase 1 is code/config-only — no new external tools, services, or runtimes introduced. Brief audit of existing dependencies relied on by Phase 1 code paths:

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 | All new modules | ✓ (assumed; Docker base is python:3.11-slim) | 3.11 per requirements.txt + Dockerfile | — |
| `pydantic` | `AgentConfig`, `ToolResult` | ✓ | `>=2.7` per requirements.txt | — |
| `openai` | `openai_adapter.py` (existing) | ✓ | `>=1.50` per requirements.txt | — |
| `httpx` | `httpx.Timeout(30.0)` | ✓ (transitive via openai) | bundled | — |
| `pandas` | `AgentContext._df_cache` type hint | ✓ | `>=2.2` per requirements.txt | — |
| `pytest` | SC verification tests | ✗ — not pinned in `requirements.txt` | — | `python -m unittest` (tests above are compatible with both if `pytest.raises` is replaced with `self.assertRaises`) — OR add `pytest` as a dev dep |

**Missing dependencies with no fallback:** None (pytest has a fallback).

**Missing dependencies with fallback:** `pytest` — can run via `python -m unittest discover tests/`. Planner should decide: add `pytest>=8.0` to a new `requirements-dev.txt`, OR convert tests to unittest-native. See § Open Questions Q1.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `openai>=1.50` accepts `timeout=httpx.Timeout(...)` as a per-request kwarg on `chat.completions.create` | § Pattern 5, SC4 | LOW — confirmed by openai-python README [CITED] and by matching examples in OpenAI Developer Community; installed version cannot be probed without venv so verification is deferred to SC4 unit test. If false, test fails at CI and planner switches to `client.with_options(timeout=...)` call form. |
| A2 | `extra_headers=None` is accepted by `chat.completions.create` (the existing `_extra_headers()` returns `None` when no headers configured) | § Pattern 5 | LOW — already works in current code (pre-Phase-1). We don't change that call; we only add a sibling kwarg. |
| A3 | `settings_page.py` auto-form-generation does NOT iterate over `AppConfig.agent.*` fields | § Pattern 4 | MEDIUM — if `settings_page.py` uses `AppConfig.__fields__` and recursively descends into Pydantic submodels, the AgentConfig fields would appear in the UI (violating OBS-03). Mitigation: read `settings_page.py` during Planner's task analysis and confirm (file was NOT in the files_to_read list, so this is unverified in this research pass). If it auto-recurses, a `settings_page.py` guard is needed before Phase 1 closes. |
| A4 | `AppConfig` currently has no `Config`/`model_config` that sets `extra="forbid"` | § Pattern 4 | LOW — verified by reading `app/core/config.py`; no ConfigDict is set, so default `"ignore"` applies. |
| A5 | Phase 4 is the correct home for `_AGENT_TRACE_KEY` creation — Phase 1 only documents | § Session-State Audit | LOW — HOME-04 / UX-03 are both Phase 4 per REQUIREMENTS.md traceability table. |
| A6 | Tests can be placed in `tests/` (directory does not exist today) without tripping CI/lint | § Recommended Project Structure | LOW — no CI config found in repo (`.github/workflows/` not present at the surface; would block Wave 2 confirm if found). No pre-existing `tests/` means no conflict. |

## Open Questions

1. **pytest vs unittest for SC1–SC4?**
   - What we know: `pytest` is not in `requirements.txt`; no `tests/` directory exists today; `nyquist_validation` is disabled in `.planning/config.json` so tests are not contractually required. But SC1–SC4 are trivially testable and would catch all listed pitfalls.
   - What's unclear: Does the project want a new `requirements-dev.txt` + `pytest>=8.0`, or should tests be written in stdlib `unittest` (works out of the box)?
   - **Recommendation:** Write tests in **stdlib `unittest` style** to match zero-new-deps constraint. Planner's AppConfig task can still `pytest`-run them if a dev env has pytest installed (pytest discovers unittest-style tests automatically). Convert the `pytest.raises` blocks in SC1 example above to `self.assertRaises(ValidationError)`.

2. **Do we update `config/settings.example.yaml` to include an `app.agent:` block as documentation?**
   - What we know: `settings.example.yaml` is an onboarding template. Adding the `app.agent:` block shows operators what's configurable without requiring them to read Python code.
   - What's unclear: Is documentation-style YAML update in scope for Phase 1, or deferred to Phase 5's doc sweep?
   - **Recommendation:** Include in Phase 1 as a single ~10-line append to `settings.example.yaml` — it's part of "OBS-03 editable via settings.yaml" deliverable. Cost is tiny.

3. **Does `settings_page.py` auto-generate a form for nested Pydantic models?**
   - What we know: OBS-03 says "not via the Settings UI in v1". `app/pages/settings_page.py` was not in `files_to_read` so its exact behavior is unknown to this researcher.
   - What's unclear: If it uses `model.model_fields.items()` and recurses into submodels (like `AppConfig.agent`), the AgentConfig fields would unintentionally surface in the UI.
   - **Recommendation:** Planner spawns a brief audit task in Wave 1 to grep `settings_page.py` for `AppConfig` / `app.` field iteration. If found recursing, add a `Field(exclude=True)` or an explicit skip-list. If not, no action. Assumption A3.

4. **Where does `_AGENT_TRACE_KEY` get defined — `session.py` or `home.py`?**
   - What we know: ARCHITECTURE.md line 343–344 says it belongs in `session.py`. HOME-04 says the trace "kept in a separate `_AGENT_TRACE_KEY` session slot keyed by turn index."
   - What's unclear: Just a Phase 4 decision — not Phase 1's problem.
   - **Recommendation:** Phase 1 documents the name and location (session.py) in this research; Phase 4 creates it.

## Validation Architecture

> **Nyquist validation is disabled** in `.planning/config.json` (`workflow.nyquist_validation: false`). Per researcher guidance, this section is **omitted** as a hard deliverable. The Code Examples section above provides four unittest-style test files that the planner SHOULD include as verification steps against SC1–SC4 anyway, because:
> - Each test is < 20 lines.
> - They directly verify the phase success criteria.
> - Phase 2 tools will rely on these contracts being correct — regression coverage is cheap insurance.
>
> If the planner prefers to treat these as "verification scripts" rather than "tests", that's fine — they execute identically with `python -m unittest tests/core/agent/test_config.py` etc.

## Security Domain

Phase 1 is a contracts phase with **zero net-new external surface** (no new endpoints, no new user input paths, no new secrets, no new file/network access). The one real security-adjacent addition is the OpenAI timeout, which is a **resilience** fix rather than a confidentiality/integrity one (it prevents unbounded hangs, not attacks).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no — no auth changes; `streamlit-authenticator` unchanged | n/a |
| V3 Session Management | **yes, informational** — session-state audit verifies no new surface introduces collision/leakage. | Session keys documented in § Session-State Audit with explicit preserve/remove/new table |
| V4 Access Control | no — no authz surface changes | n/a |
| V5 Input Validation | **yes** — `AgentConfig` fields use Pydantic `ge`/`le` bounds to prevent misconfiguration (e.g., `max_steps=0` DoS via dead loop). `ToolResult.content` is `str` (no structured deserialization). | Pydantic 2 `Field(ge=..., le=...)` at model definition; rejects at construction time |
| V6 Cryptography | no — no crypto introduced | n/a (OpenAI API uses HTTPS via httpx, unchanged) |
| V14 Configuration | **yes** — `AppConfig.agent` adds fields persisted in YAML. Secrets (API keys) are not stored here; `OPENAI_API_KEY` continues to be read from env/LLMConfig.api_key, untouched by Phase 1. | No secrets in AgentConfig by design; allowed_tables allowlist codified (used by Phase 2 SAFE-01) |

### Known Threat Patterns for Python 3.11 + Pydantic 2 + OpenAI SDK

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Denial of service via unbounded OpenAI call | DoS | `timeout=httpx.Timeout(30.0)` per-request — AGENT-08, landing this phase |
| Configuration injection via YAML (operator supplies malicious `allowed_tables`) | Tampering | Defense in depth — Phase 2 `run_sql` tool validates the actual SQL against `config.allowed_tables` via `sqlparse` walker (SAFE-01). Phase 1 only defines the field; the enforcement point is in the tool. |
| Type confusion on `ToolResult.chart: Any` | Tampering | `arbitrary_types_allowed=True` relaxes Pydantic type checking for this field. Phase 2 `make_chart` is the only constructor of `chart`; the string path (content) is always `str`. Tolerated because the field never crosses the network boundary — it's consumed by `st.plotly_chart()` locally. |
| Protocol spoofing — arbitrary object claims to be a `Tool` | Spoofing | Phase 2's `TOOL_REGISTRY` is a hand-enumerated dict. An arbitrary object cannot inject itself at runtime. `@runtime_checkable` isinstance is a structural check, not an authorization check — acknowledged. |

No security controls in `CLAUDE.md` beyond the v1 constraints already reflected in the project spec. No security-enforcement config flag was set in `.planning/config.json`, so this section is informational; Phase 2's SAFE-01 through SAFE-07 are the enforcement layer.

## Wave / Parallelization Proposal

Granularity is `coarse` + `parallelization: true` per `.planning/config.json`. Phase 1 work decomposes cleanly into parallelizable file-scoped tasks.

**Wave 1 (all parallel — no mutual dependencies):**

| Task | Creates / Modifies | Depends on |
|------|-------------------|-----------|
| T1.1 — AgentConfig | `app/core/agent/__init__.py` (empty), `app/core/agent/config.py` (new), `tests/core/agent/test_config.py` (new) | Nothing |
| T1.2 — AgentContext | `app/core/agent/context.py` (new), `tests/core/agent/test_context.py` (new) | T1.1 (imports `AgentConfig`) — but can be written against a forward reference; tests import after Wave 1 ends |
| T1.3 — Tool Protocol + ToolResult | `app/core/agent/tools/__init__.py` (empty), `app/core/agent/tools/_base.py` (new), `tests/core/agent/test_tools_base.py` (new) | T1.2 (imports `AgentContext`) — same forward-ref caveat |
| T1.4 — openai_adapter timeout | `app/adapters/llm/openai_adapter.py` (modified), `tests/core/agent/test_openai_timeout.py` (new) | Nothing (independent of T1.1–T1.3) |
| T1.5 — Session-state audit | `.planning/phases/01-foundation/SUMMARY.md` or similar audit artifact (no code change) | Nothing (reads files only) |

**Wave 1 coordination:** T1.1, T1.4, T1.5 are truly independent. T1.2 imports from T1.1; T1.3 imports from T1.2. Three options:

- **Option A (strict dependency chain):** T1.1 → T1.2 → T1.3 serially; T1.4 + T1.5 parallel to the chain. Safe but slower.
- **Option B (optimistic parallel):** All five in parallel; the Planner pre-specs the `AgentConfig` and `AgentContext` interface shapes in the plan so each task writer works against a known contract. Fast but requires clean interface spec upfront. **Recommended for `coarse` + `parallelization: true`.**
- **Option C (batched):** T1.1 + T1.4 + T1.5 in Wave 1a; T1.2 + T1.3 in Wave 1b. Middle ground.

**Recommend Option B.** This research provides complete interface specs above (`AgentConfig` field list with types, `AgentContext` fields, `Tool` Protocol signature) so Wave 1 tasks can be spawned concurrently. The unit tests import the actual modules once they're written, so test execution naturally serializes after all Wave 1 files land.

**Wave 2 (sequential, after Wave 1 complete):**

| Task | Modifies | Depends on |
|------|----------|-----------|
| T2.1 — AppConfig composition | `app/core/config.py` (add `agent: AgentConfig` field), `config/settings.example.yaml` (add docs block), new `tests/core/test_app_config.py` (YAML round-trip test) | T1.1 (AgentConfig must exist) |
| T2.2 — (conditional) `settings_page.py` guard | `app/pages/settings_page.py` — IF A3 audit shows it auto-recurses into nested Pydantic models | T2.1 + A3 audit result |

**Wave 3 (phase closure):**

| Task | Action | Depends on |
|------|--------|-----------|
| T3.1 — SC1–SC5 verification | Run all 4+ test files; execute SC5 grep audit; collect results in a phase completion note | All Waves 1 + 2 |

**Rationale for this split:**
- Wave 1 is 4–5 parallel file creations with zero cross-file coupling (given the interface spec in this research). Maximum parallelism.
- Wave 2 is the one integration point where all Wave 1 outputs converge via `AppConfig`. Serial.
- Wave 3 is verification. Lightweight.

**Alternative (simpler) split considered and rejected:** Single-wave sequential — each file one at a time. Rejected because it ignores `parallelization: true` config and wastes ~3× wall-clock.

**Alternative (finer) split considered and rejected:** Separate `tests/core/agent/__init__.py` as its own task. Rejected because empty package markers are trivial and can be bundled with the first test task.

## Sources

### Primary (HIGH confidence)

- `.planning/REQUIREMENTS.md` — AGENT-07, AGENT-08, AGENT-09, OBS-03 definitions [VERIFIED: file read]
- `.planning/research/SUMMARY.md` — phase structure, stack, pitfalls, `httpx.Timeout(30.0)` convention [VERIFIED: file read]
- `.planning/research/ARCHITECTURE.md` — file tree, component boundaries, AgentContext + Tool patterns [VERIFIED: file read]
- `.planning/research/PITFALLS.md` (not re-read this pass; summarized via SUMMARY.md §Critical Pitfalls) [VERIFIED: indirect via SUMMARY]
- `.planning/phases/01-foundation/01-CONTEXT.md` — locked decisions [VERIFIED: file read]
- `app/core/config.py` — existing Pydantic patterns [VERIFIED: file read]
- `app/adapters/llm/openai_adapter.py` — 2 modification call sites confirmed [VERIFIED: lines 50 and 61]
- `app/adapters/llm/base.py` — `LLMAdapter` ABC for `AgentContext.llm_adapter` typing [VERIFIED: file read]
- `app/adapters/db/base.py` — `DBAdapter` ABC for `AgentContext.db_adapter` typing [VERIFIED: file read]
- `app/core/session.py` — existing session-state keys [VERIFIED: file read]
- `app/pages/home.py` — legacy keys for audit [VERIFIED: file read]
- `app/pages/{explorer,compare}.py` — additional session keys [VERIFIED: grep]
- `requirements.txt` — pinned versions [VERIFIED: file read]
- `config/settings.example.yaml` — YAML format reference [VERIFIED: file read]

### Secondary (MEDIUM confidence)

- [OpenAI Python API library (PyPI)](https://pypi.org/project/openai/) — `timeout` parameter supports `httpx.Timeout` per-request
- [OpenAI Developer Community — Configuring timeout for ChatCompletion Python](https://community.openai.com/t/configuring-timeout-for-chatcompletion-python/107226) — community confirmation
- [Pydantic docs — Fields (default_factory)](https://docs.pydantic.dev/latest/concepts/fields/) — `default_factory` best practice
- [Pydantic docs — Models (nested validation, extra='ignore' default)](https://docs.pydantic.dev/latest/concepts/models/) — nested model defaults applied when YAML key missing
- [Python typing docs — Protocol and runtime_checkable](https://docs.python.org/3/library/typing.html) — structural typing semantics

### Tertiary (LOW confidence)

- [How to Give a Pydantic List Field a Default Value](https://www.pythontutorials.net/blog/how-to-give-a-pydantic-list-field-a-default-value/) — best-practice confirmation (repeats Pydantic docs)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already pinned; Context7 not consulted because the items are standard Python stdlib / well-documented Pydantic 2 / OpenAI SDK features, verified against multiple sources and existing codebase usage.
- Architecture: HIGH — direct carryover from ARCHITECTURE.md with one documented divergence (CONTEXT.md overrides hand-authored `schema: dict` in favor of Pydantic `args_model`).
- Pitfalls: HIGH — all 6 listed pitfalls are either stdlib-documented (mutable default, runtime_checkable) or project-specific (home.py legacy keys) and verified by grep.
- Session audit: HIGH — full grep of `app/` produced the canonical key list [VERIFIED].
- YAML round-trip safety: MEDIUM-HIGH — A3 (settings_page.py auto-form) is the one unverified assumption; planner should audit before Wave 2.

**Research date:** 2026-04-23
**Valid until:** 2026-05-23 (30 days — stable foundation; no fast-moving libraries in the Phase 1 scope)

---

**Addresses REQ: [AGENT-07, AGENT-08, AGENT-09, OBS-03]**
