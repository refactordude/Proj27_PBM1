# Architecture Research

**Domain:** Agentic ReAct loop layered into an existing Streamlit adapter-based data platform
**Researched:** 2026-04-22
**Confidence:** HIGH (based on direct codebase analysis + established ReAct/tool-calling patterns)

---

## System Overview

The proposed architecture adds a new `app/core/agent/` sub-package to the existing Core layer. The agent module consumes the existing DB and LLM adapters through an `AgentContext` dependency container — never importing concrete adapter classes directly. The Streamlit Home page becomes a thin rendering harness that drives the loop and streams the trace UI.

```
┌───────────────────────────────────────────────────────────────────┐
│                     Presentation Layer (UI)                       │
│  app/pages/home.py  ← REWRITTEN (agent harness + trace renderer)  │
└───────────────────────────────┬───────────────────────────────────┘
                                │ calls run_agent_turn() / streams steps
┌───────────────────────────────▼───────────────────────────────────┐
│                     Core / Agent Sub-layer                         │
│  app/core/agent/                                                   │
│  ┌──────────────┐  ┌─────────────────┐  ┌───────────────────────┐  │
│  │  loop.py     │  │  context.py     │  │  prompt.py            │  │
│  │ (ReAct loop) │  │ (AgentContext)  │  │ (system prompt +      │  │
│  └──────┬───────┘  └────────┬────────┘  │  tool schemas)        │  │
│         │                   │           └───────────────────────┘  │
│  ┌──────▼───────────────────▼──────────────────────────────────┐   │
│  │                  tools/                                      │   │
│  │  run_sql.py  get_schema.py  pivot_to_wide.py                 │   │
│  │  normalize_result.py  get_schema_docs.py  make_chart.py      │   │
│  └──────────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬───────────────────────────────────┘
                                │ uses via AgentContext (protocol)
┌───────────────────────────────▼───────────────────────────────────┐
│                    Existing Adapter Layer (UNCHANGED)              │
│  app/adapters/db/    mysql.py  registry.py  base.py (DBAdapter)   │
│  app/adapters/llm/   openai_adapter.py  registry.py  base.py      │
└───────────────────────────────────────────────────────────────────┘
│                    Existing Core (UNCHANGED)                       │
│  sql_safety.py  logger.py  session.py  config.py  runtime.py      │
└───────────────────────────────────────────────────────────────────┘
```

---

## Proposed File Tree

All new files. No existing files are modified except `app/pages/home.py` (rewritten) and `app/core/config.py` (AgentConfig fields appended).

```
app/
├── core/
│   ├── agent/
│   │   ├── __init__.py          # empty package marker
│   │   ├── context.py           # AgentContext dataclass (DI container)
│   │   ├── loop.py              # run_agent_turn() — the ReAct loop
│   │   ├── prompt.py            # build_system_prompt() + build_tool_schemas()
│   │   └── tools/
│   │       ├── __init__.py      # exports Tool protocol + registry dict
│   │       ├── _base.py         # Tool Protocol definition + ToolResult dataclass
│   │       ├── run_sql.py       # run_sql tool implementation
│   │       ├── get_schema.py    # get_schema tool implementation
│   │       ├── pivot_to_wide.py # pivot_to_wide tool implementation
│   │       ├── normalize_result.py # normalize_result tool implementation
│   │       ├── get_schema_docs.py  # get_schema_docs tool implementation
│   │       └── make_chart.py    # make_chart tool implementation
│   ├── config.py                # MODIFIED: AgentConfig fields added
│   ├── logger.py                # UNCHANGED (log_query / log_llm reused)
│   ├── runtime.py               # UNCHANGED
│   ├── session.py               # MODIFIED: agent trace state helpers added
│   ├── sql_safety.py            # UNCHANGED
│   └── auth.py                  # UNCHANGED
└── pages/
    └── home.py                  # REWRITTEN: agent harness, trace renderer
```

New test files:

```
tests/
├── agent/
│   ├── test_run_sql.py
│   ├── test_get_schema.py
│   ├── test_pivot_to_wide.py
│   ├── test_normalize_result.py
│   ├── test_get_schema_docs.py
│   ├── test_make_chart.py
│   └── test_loop.py             # integration test with mocked OpenAI client
```

---

## Component Boundaries

### What Each Component Owns

| Component | Owns | Does NOT own |
|-----------|------|--------------|
| `loop.py` | ReAct iteration (messages list, tool dispatch, step counter, budget enforcement, timeout, streaming) | Tool logic, UI rendering, prompt text |
| `context.py` | Binding of resolved DB/LLM adapters + budget config into one injectable object | Adapter construction, session state |
| `prompt.py` | System prompt string, tool schema list for `tools=[...]`, UFS-specific instructions | Token counting, chat history management |
| Each `tools/*.py` | One tool's execution logic and its JSON schema descriptor | Loop control, adapter construction, session state |
| `home.py` | Streamlit rendering — trace stream, expander collapse, final chart, chat history persistence | Agent execution logic |
| `session.py` | Session-state keys for chat history, recent queries, agent trace | Agent execution logic |

### Adapter Pattern Preservation

Tools access DB and LLM exclusively through `AgentContext`, which is typed against the abstract base classes (`DBAdapter`, `LLMAdapter`) from `app/adapters/db/base.py` and `app/adapters/llm/base.py`. No tool file imports `MySQLAdapter` or `OpenAIAdapter` directly. This means any future DB or LLM adapter registered in the existing registry will automatically be available to the agent without modifying any tool.

The one current exception by design: the loop calls the raw OpenAI `chat.completions` API directly (not through `LLMAdapter.generate_sql`) because `generate_sql` does not support tool-calling. This call is isolated in `loop.py` and guarded behind an `isinstance(ctx.llm_adapter, OpenAIAdapter)` check that raises `AgentUnsupportedAdapterError` immediately if a non-OpenAI adapter is selected. Explorer, Compare, and Settings continue to use `LLMAdapter.generate_sql` / `stream_text` unchanged.

---

## Pattern Designs

### Pattern 1: AgentContext as Dependency Container

`AgentContext` is a plain `dataclass` (not a registry, not a singleton). It is constructed in `home.py` from already-resolved adapters and passed into `run_agent_turn()` and all tools. Tools receive only `AgentContext` — never the raw adapters.

```python
# app/core/agent/context.py
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.adapters.db.base import DBAdapter
from app.adapters.llm.base import LLMAdapter
from app.core.config import AgentConfig


@dataclass
class AgentContext:
    db_adapter: DBAdapter
    llm_adapter: LLMAdapter
    db_name: str
    user: str
    config: AgentConfig
    # Ephemeral per-turn DataFrame cache keyed by tool_call_id
    _df_cache: dict[str, pd.DataFrame] = field(default_factory=dict)

    def store_df(self, tool_call_id: str, df: pd.DataFrame) -> None:
        self._df_cache[tool_call_id] = df

    def get_df(self, tool_call_id: str) -> pd.DataFrame | None:
        return self._df_cache.get(tool_call_id)
```

Rationale: a dataclass is simpler than a Protocol and is directly testable by construction in unit tests. The `_df_cache` is per-context, so it is per-turn by design (stateless across turns without special cleanup).

### Pattern 2: Tool Protocol + Flat Registry Dict

Tools implement a `Tool` Protocol (structural typing) and are registered in a flat dict in `tools/__init__.py`. This mirrors the existing `db/registry.py` and `llm/registry.py` pattern but uses a simpler dict (not a class-based factory) because tools are pure functions, not stateful adapter instances.

```python
# app/core/agent/tools/_base.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import pandas as pd

from app.core.agent.context import AgentContext


@dataclass
class ToolResult:
    content: str                        # text returned to the model
    df: pd.DataFrame | None = None      # optional DataFrame for chart handoff
    chart: Any | None = None            # optional Plotly figure


@runtime_checkable
class Tool(Protocol):
    name: str
    schema: dict                        # OpenAI tool schema dict

    def __call__(self, ctx: AgentContext, **kwargs: Any) -> ToolResult: ...
```

```python
# app/core/agent/tools/__init__.py
from app.core.agent.tools.run_sql import RunSqlTool
from app.core.agent.tools.get_schema import GetSchemaTool
from app.core.agent.tools.pivot_to_wide import PivotToWideTool
from app.core.agent.tools.normalize_result import NormalizeResultTool
from app.core.agent.tools.get_schema_docs import GetSchemaDocsTool
from app.core.agent.tools.make_chart import MakeChartTool

TOOL_REGISTRY: dict[str, Tool] = {
    t.name: t
    for t in [
        RunSqlTool(),
        GetSchemaTool(),
        PivotToWideTool(),
        NormalizeResultTool(),
        GetSchemaDocsTool(),
        MakeChartTool(),
    ]
}
```

Each tool class is instantiated once at import time and is stateless (all state is in `AgentContext`). Registering a new tool is one line in `__init__.py` and one new file in `tools/`.

### Pattern 3: Per-Turn DataFrame Cache via AgentContext

The `data_ref` argument of the `make_chart` tool needs to reference a DataFrame produced by an earlier tool call in the same turn. Rather than inventing cross-turn IDs (out of scope for v1), the cache lives on `AgentContext._df_cache` keyed by `tool_call_id` (the string the OpenAI API assigns to each tool call). This is strictly ephemeral — the `AgentContext` object is created fresh in `home.py` for every user turn, so there is no cross-turn leakage.

```python
# Inside run_sql tool, after executing query:
ctx.store_df(tool_call_id, df)
return ToolResult(content=f"{len(df)} rows returned.", df=df)

# Inside make_chart tool:
df = ctx.get_df(kwargs["data_ref"])  # data_ref == tool_call_id of run_sql/pivot step
```

### Pattern 4: Budget and Timeout Enforcement

Two kill-switches, both in `loop.py`:

1. **Step budget** (`max_steps`): loop counter checked at the top of each iteration. Raises `AgentBudgetError` when exceeded. This is in the loop, not individual tools, because budget is a loop-level policy.

2. **Per-turn wall-clock timeout** (`timeout_s`): `time.perf_counter()` captured at turn start, checked before each OpenAI call. Raises `AgentTimeoutError`. Also applied to the OpenAI call itself via `client.chat.completions.create(timeout=timeout_s)` — this is the missing timeout identified in the codebase concerns.

The `run_sql` tool additionally enforces `row_cap=200` and the table allowlist `["ufs_data"]` as a second independent defense layer. If the query returns more rows than `row_cap`, the tool returns a refine signal instead of truncated data, forcing the model to write an aggregating query.

### Pattern 5: System Prompt and Tool Schemas

`prompt.py` builds both at import time (static computation). The system prompt is a module-level constant string incorporating UFS schema awareness, the table allowlist, and the per-turn budget. Tool schemas are collected from `TOOL_REGISTRY` at import time. Neither depends on runtime state.

```python
# app/core/agent/prompt.py
from __future__ import annotations

from app.core.agent.tools import TOOL_REGISTRY

AGENT_SYSTEM_PROMPT: str = (
    "당신은 UFS 벤치마크 데이터베이스 전문 분석 에이전트입니다.\n"
    "허용된 테이블: ufs_data (단일 테이블).\n"
    "허용된 작업: SELECT 전용 (읽기).\n"
    # ... UFS domain instructions, Result field quirks, pivot idiom ...
)

def build_tool_schemas() -> list[dict]:
    return [t.schema for t in TOOL_REGISTRY.values()]
```

Rationale: Pydantic-generated JSON schemas are unnecessary overhead for 6 hand-authored tools with stable signatures. Hand-written dicts kept in each tool file as `schema: dict = {...}` class attribute. This matches the project's "no extra frameworks" constraint.

---

## Data Flow: User Question → Final Answer

```
home.py receives st.chat_input question
    │
    ├─ resolve_selected_db(s)        → db_adapter, db_name
    ├─ resolve_selected_llm(s)       → llm_adapter (must be OpenAIAdapter)
    │
    ├─ AgentContext(db_adapter, llm_adapter, db_name, user, config)
    │
    └─ run_agent_turn(ctx, question, history)   [loop.py]
           │
           ├─ Build messages: system_prompt + chat_history + user question
           ├─ LOOP (step=0..max_steps):
           │     │
           │     ├─ client.chat.completions.create(
           │     │       messages, tools=build_tool_schemas(),
           │     │       stream=True, timeout=ctx.config.timeout_s
           │     │   )
           │     │
           │     ├─ STREAM response chunks → yield AgentStep(type="thinking", chunk=...)
           │     │       └─ home.py renders live text in st.empty()
           │     │
           │     ├─ If finish_reason == "stop":
           │     │       └─ yield AgentStep(type="final_answer", text=...)
           │     │              └─ loop exits
           │     │
           │     └─ For each tool_call in response.tool_calls:
           │           │
           │           ├─ log_llm(user, model, question, tool=tool_name, ...)
           │           ├─ tool = TOOL_REGISTRY[tool_call.function.name]
           │           ├─ result: ToolResult = tool(ctx, **json.loads(args))
           │           │
           │           ├─ If result.df is not None:
           │           │       ctx.store_df(tool_call_id, result.df)
           │           │
           │           ├─ If result.chart is not None:
           │           │       yield AgentStep(type="chart", figure=result.chart)
           │           │              └─ home.py: st.plotly_chart(figure)
           │           │
           │           ├─ log_query(user, db_name, sql, rows, ...)  [for run_sql only]
           │           │
           │           ├─ yield AgentStep(type="tool_result", name=..., summary=...)
           │           │       └─ home.py: renders tool badge + row count
           │           │
           │           └─ Append tool result to messages list
           │
           └─ If budget/timeout exceeded:
                   └─ yield AgentStep(type="error", reason=...)

home.py after run_agent_turn() completes:
    ├─ Collapse all intermediate AgentStep renders into st.expander("실행 추적")
    ├─ Show final answer text in st.chat_message("assistant")
    ├─ append_chat("user", question) + append_chat("assistant", final_text)
    └─ record_recent_query(last_sql, db_name, rows)
```

### Logging Hooks

- `log_llm` fires once per OpenAI API call (at the start of each loop iteration), capturing model, question, step index, and duration.
- `log_query` fires once per `run_sql` tool invocation, capturing the sanitized SQL, row count, and duration.
- Neither logging call is inside the streaming path — they fire after the response is complete for each step.

---

## Old Home Flow Removal Plan

The existing `app/pages/home.py` (165 lines) is fully replaced. The following are deleted:

| Removed element | Rationale |
|-----------------|-----------|
| `pending_sql` session state + text area + Execute/Discard buttons | User-confirm step is replaced by autonomous loop |
| `llm_adapter.generate_sql()` call | The loop calls raw `chat.completions` directly |
| `extract_sql_from_response()` import | SQL comes from tool-call arguments, not prose |
| `auto_chart()` call | Replaced by `make_chart` tool result |
| `validate_and_sanitize()` call in home.py | Moved inside `run_sql` tool; safety unchanged |

The following session state is preserved unchanged:

| Preserved | Where | Notes |
|-----------|-------|-------|
| `get_chat_history()` / `append_chat()` | `app/core/session.py` | Agent answers appended as before |
| `record_recent_query()` | `app/core/session.py` | Called once per turn with the last executed SQL |
| `recent_queries()` display block | `home.py` | Bottom-of-page section preserved |
| `reset_chat()` button | `home.py` | Preserved |

One new session state key is added to `session.py`:

```python
_AGENT_TRACE_KEY = "agent_trace"   # list[AgentStep] — cleared at turn start
```

This holds the live trace for collapsing into the expander after the final answer. It is cleared at the start of each new turn, not carried across turns.

---

## Build Order (Dependency Graph)

Dependencies flow strictly bottom-up. Build in this sequence:

```
1. app/core/config.py           ADD AgentConfig (max_steps, row_cap, timeout_s)
   └── No dependencies on new code

2. app/core/agent/context.py    NEW — depends on config.AgentConfig, adapter base classes
   └── Depends on: config.py (step 1), adapters/*/base.py (existing)

3. app/core/agent/tools/_base.py  NEW — Tool Protocol + ToolResult
   └── Depends on: context.py (step 2)

4. app/core/agent/tools/*.py    NEW — 6 tool implementations
   └── Depends on: _base.py (step 3), context.py (step 2)
   └── run_sql.py also depends on: sql_safety.py (existing)
   └── make_chart.py also depends on: utils/viz.py concepts (may reuse or inline)
   └── All can be built and unit-tested in parallel once steps 2-3 are done

5. app/core/agent/tools/__init__.py  NEW — TOOL_REGISTRY assembly
   └── Depends on: all 6 tool files (step 4)

6. app/core/agent/prompt.py     NEW — system prompt + tool schema builder
   └── Depends on: TOOL_REGISTRY (step 5)

7. app/core/agent/loop.py       NEW — run_agent_turn()
   └── Depends on: context.py (step 2), TOOL_REGISTRY (step 5), prompt.py (step 6)
   └── Depends on: openai SDK (existing), logger.py (existing)

8. app/core/session.py          MODIFY — add _AGENT_TRACE_KEY helpers
   └── Depends on: nothing new (Streamlit session_state)

9. tests/agent/test_*.py        NEW — unit tests for each tool + loop integration test
   └── Build in parallel with or immediately after each tool (step 4)
   └── test_loop.py requires: all of steps 2-7

10. app/pages/home.py           REWRITE — agent harness + trace UI
    └── Depends on: loop.py (step 7), session.py (step 8)
    └── This is the last step — all business logic is tested before the UI is wired up
```

The UI rewrite (`home.py`) is the final step, ensuring all logic is unit-testable before the Streamlit integration is done.

---

## Architectural Patterns to Follow

### Follow: Existing Registry Pattern

The flat `TOOL_REGISTRY` dict mirrors `app/adapters/db/registry.py` and `app/adapters/llm/registry.py` in shape. Adding a new tool is the same motion as adding a new adapter: one file, one registration line. The loop never hard-codes tool names; it dispatches by `TOOL_REGISTRY[function_name]`.

### Follow: SafetyResult Pattern for Tool Returns

`ToolResult` mirrors `SafetyResult` — a dataclass with a small set of typed fields. This is consistent with CONVENTIONS.md ("Complex returns use dataclasses or named tuples over bare tuples").

### Follow: keyword-only parameters in all public APIs

All tool `__call__` signatures accept `**kwargs` internally but tools expose their parameters via the JSON schema, not Python signatures. The `run_agent_turn()` function and `AgentContext` constructor use keyword-only args where applicable, consistent with `log_query(*, user, database, sql, ...)`.

### Follow: module docstrings in Korean

Each new module gets a Korean docstring explaining purpose and design decisions, consistent with existing files (`"""MySQL DB 어댑터...."""`, `"""쿼리·LLM 호출 로깅..."""`).

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Tool imports concrete adapters

**What people do:** `from app.adapters.llm.openai_adapter import OpenAIAdapter` inside a tool, then call `openai_adapter.client.chat.completions.create(...)` directly.

**Why it's wrong:** Breaks the adapter abstraction. Makes tools untestable without a live OpenAI client. If the loop ever adds Anthropic support, all tools need updating.

**Do this instead:** Tools receive `AgentContext.db_adapter` (typed as `DBAdapter`). Only `loop.py` needs awareness that the current provider must be OpenAI (checked once at loop entry).

### Anti-Pattern 2: DataFrame stored in session_state across turns

**What people do:** `st.session_state["result_df"] = df` after a query, then reference it in the next turn.

**Why it's wrong:** Creates implicit cross-turn coupling. Grows session memory unboundedly. Contradicts the v1 stateless-per-turn decision.

**Do this instead:** DataFrames live only in `AgentContext._df_cache` during the current turn. `AgentContext` is garbage-collected when `run_agent_turn()` returns.

### Anti-Pattern 3: Inline tool logic in loop.py

**What people do:** Implement `run_sql`, `make_chart` etc. as `if/elif` branches inside the loop dispatcher.

**Why it's wrong:** Makes tools untestable in isolation. Violates single-responsibility. Makes adding a new tool a surgery on the loop.

**Do this instead:** One tool = one file. Loop dispatches via `TOOL_REGISTRY[name](ctx, **kwargs)`.

### Anti-Pattern 4: Baking schema docs into system prompt

**What people do:** Include all 7 UFS schema spec sections in the system prompt every turn.

**Why it's wrong:** ~2-5k tokens burned on every API call, even for simple questions that don't need normalization rules. The `get_schema_docs` tool lets the agent pull only the section it needs.

**Do this instead:** System prompt includes table/column structure only. Schema spec sections are served on demand via `get_schema_docs(section=N)`.

### Anti-Pattern 5: Validating SQL inside home.py

**What people do:** Call `validate_and_sanitize()` in the page layer before passing to the DB adapter.

**Why it's wrong (for the agent path):** In the agent path, the SQL source is a tool-call argument (not user-typed text), but safety validation is still required. If validation is in the page, tests cannot verify the agent enforces it without spinning up Streamlit.

**Do this instead:** `run_sql` tool calls `validate_and_sanitize()` + table allowlist check internally. Safety is enforced regardless of how the tool is invoked (from the loop, from a test, or from a future CLI).

---

## Integration Points

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `loop.py` ↔ `tools/` | `Tool.__call__(ctx, **kwargs) -> ToolResult` | Protocol-typed; no coupling |
| `loop.py` ↔ OpenAI SDK | `client.chat.completions.create(stream=True, tools=...)` | Isolated in loop.py only |
| `loop.py` ↔ `home.py` | `Generator[AgentStep, None, None]` — `yield` from loop, render in page | Decoupled; loop is Streamlit-free |
| `tools/run_sql.py` ↔ `sql_safety.py` | `validate_and_sanitize(sql, default_limit=ctx.config.row_cap)` | Existing function, unchanged |
| `tools/run_sql.py` ↔ `DBAdapter` | `ctx.db_adapter.run_query(sanitized_sql)` | Via context, adapter-agnostic |
| `home.py` ↔ `session.py` | `append_chat()`, `record_recent_query()`, trace key helpers | Unchanged for chat; one new key |
| `home.py` ↔ `runtime.py` | `resolve_selected_db()`, `resolve_selected_llm()` | Unchanged |

### AgentConfig Addition to config.py

Three fields appended to `AppConfig` (or a new nested `AgentConfig` class inside `AppConfig`):

```python
class AgentConfig(BaseModel):
    max_steps: int = 5
    row_cap: int = 200
    timeout_s: int = 30
    table_allowlist: list[str] = Field(default_factory=lambda: ["ufs_data"])
```

These become `s.app.agent` and flow into `AgentContext.config`. Settings UI exposes them automatically via existing form generation in `settings_page.py` (no changes required there).

---

## Scaling Considerations

This is an internal tool with a single-digit concurrent user count. Scaling is not a near-term concern. The relevant operational boundary is per-turn cost:

| Concern | Current design | When to revisit |
|---------|---------------|-----------------|
| Token cost per turn | `get_schema_docs` on-demand keeps it low | If average turns exceed 5 tool calls consistently |
| OpenAI rate limits | Single user, single key — not an issue | If concurrent users > 5 |
| DataFrame memory | Per-turn context, GC'd after turn | If pivot results exceed ~50k rows (row_cap prevents this) |
| Streamlit session memory | Trace stored per session, cleared each turn | If session count > ~50 concurrent |

---

## Sources

- Codebase direct analysis: `app/adapters/`, `app/core/`, `app/pages/home.py` (2026-04-22)
- OpenAI tool-calling API: `tools=[...]` parameter in `chat.completions.create` — supported in OpenAI SDK 1.50+ (confirmed in requirements.txt)
- ReAct pattern (Yao et al., 2022) — reasoning + acting loop; adapted here to OpenAI function-calling mechanics
- Existing safety chain: `sql_safety.py` + `MySQLAdapter.run_query` readonly enforcement — preserved unchanged

---

*Architecture research for: Agentic ReAct engine on Streamlit adapter-based platform*
*Researched: 2026-04-22*
