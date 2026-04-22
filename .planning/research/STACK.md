# Stack Research

**Domain:** Agentic ReAct loop over OpenAI tool-calling, embedded in Streamlit internal data platform
**Researched:** 2026-04-22
**Confidence:** HIGH (core SDK and Streamlit primitives verified against official docs and current releases; model pricing verified against third-party aggregators cross-referenced with official OpenAI announcements)

---

## Context: This Is an Additive Milestone

The existing stack (Python 3.11, Streamlit 1.40+, SQLAlchemy 2, pymysql, Pydantic 2, openai 1.50+, Plotly, bcrypt, pandas) stays pinned. This research covers only what is needed to layer a ReAct loop on top. **No new pip dependencies are required** — every capability described below is already available inside the current `requirements.txt`.

---

## Recommended Stack

### Core Technologies

| Technology | Version Pin | Purpose | Why Recommended |
|------------|-------------|---------|-----------------|
| `openai` | `>=1.50` (already pinned) | `chat.completions.create` with `tools=[...]`; streaming chunks; automatic retry | SDK 1.50+ ships fully typed `ChatCompletionToolParam` TypedDicts, built-in exponential-backoff retry (2 attempts, 429/5xx), `APITimeoutError` for timeout handling, and `parallel_tool_calls` parameter support. No framework needed on top. |
| `streamlit` | `>=1.40` (already pinned) | `st.status`, `st.write_stream`, `st.chat_message`, `st.expander`, `st.session_state` | These five primitives together cover live agent trace streaming + collapsible post-run trace. `st.status` doubles as a live expander with `state="running"/"complete"/"error"`. No third-party streaming UI library needed. |
| `pydantic` | `>=2.7` (already pinned) | Tool argument validation after JSON parse; typed `AppConfig` fields for `max_steps`, `row_cap`, `timeout_s` | Already used project-wide. Use `model_json_schema()` to generate the `parameters` block for each tool definition — one authoritative source of truth for both the OpenAI schema and runtime validation. |
| `pandas` | `>=2.2` (already pinned) | `pivot_to_wide` tool: long→wide DataFrame pivot; `normalize_result` tool: clean/coerce the `Result` column | `DataFrame.pivot_table` handles the UFS long/narrow → wide transform natively. Bounded by `row_cap=200` so memory is not a concern. |
| `plotly` | `>=5.22` (already pinned) | `make_chart` tool: construct bar/line/scatter/heatmap figures from LLM-specified arguments | Already wired into `app/utils/viz.py`; `go.Figure` + `px.*` cover all four required chart types. The agent specifies `chart_type`, `x`, `y`, `color`, `title` — Plotly renders it. |

### Supporting Libraries (all already in requirements.txt)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sqlparse` | `>=0.5` | Already used by `sql_safety.validate_and_sanitize` | Stays unchanged; the agent path routes SQL through the existing safety layer, so no new SQL parsing is needed. |
| `pytest` | stdlib / dev dep | Unit + integration tests for each new tool and the agent loop | Use with `unittest.mock.MagicMock` to stub `client.chat.completions.create` return values. No new test library needed. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `pytest` + `unittest.mock` | Mock OpenAI responses for tool call tests | Build `make_tool_call_response(name, args)` helpers returning `MagicMock` objects with `.choices[0].message.tool_calls[0].function.{name,arguments}` populated. No dedicated OpenAI mock plugin needed — `openai-responses` (v0.13.1) is in maintenance mode and adds unnecessary dependency. |
| `httpx.Timeout` | Per-request timeout control | Pass `timeout=httpx.Timeout(30.0)` to `client.chat.completions.create(...)` to honour the `timeout_s=30` budget constraint from `AppConfig`. `httpx` is a transitive dependency of the `openai` SDK — no install needed. |

---

## OpenAI SDK Tool-Calling API Shape

**Confidence: HIGH** — verified against SDK source (indexed 2026-01-12, commit 722d3f) and community discussions.

### Tool Definition

```python
from openai.types.chat import ChatCompletionToolParam

TOOLS: list[ChatCompletionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "run_sql",           # a-z, A-Z, 0-9, _, - only; max 64 chars
            "description": "Execute a SELECT query against ufs_data.",
            "parameters": RunSqlArgs.model_json_schema(),   # Pydantic v2
        },
    },
    ...
]
```

Use `Pydantic BaseModel.model_json_schema()` to generate the `parameters` block — this keeps the schema in sync with runtime validation automatically. Do not hand-write raw JSON schemas.

### Call Shape (non-streaming)

```python
response = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=messages,
    tools=TOOLS,
    tool_choice="auto",          # or "required" to force a tool call
    parallel_tool_calls=False,   # set False for sequential ReAct loop
    timeout=httpx.Timeout(30.0),
    max_tokens=1024,
)
finish = response.choices[0].finish_reason   # "tool_calls" | "stop" | "length"
msg   = response.choices[0].message
```

`finish_reason == "tool_calls"` signals the model wants to invoke tools. `finish_reason == "stop"` is the terminal step — emit final answer.

### `parallel_tool_calls`

Default is `True` in the SDK (the model may return multiple tool calls in one response). For a sequential ReAct loop where tool results gate the next step, **set `parallel_tool_calls=False`** — this guarantees at most one tool per turn, simplifying the dispatch loop and making `max_steps` accounting exact. If future phases need parallel calls (e.g., fetching schema sections concurrently), re-enable per-call.

### Streaming Tool Calls (for live trace UX)

Streaming with `stream=True` is optional for this milestone's UX. The recommended approach is:

1. Use **non-streaming** for each tool-call turn (model → tool dispatch is fast; the latency win from streaming is minimal for JSON arguments).
2. Use **streaming** only for the final `finish_reason == "stop"` turn to typewriter-effect the answer text into `st.write_stream`.

If streaming tool calls are needed in future (to show argument construction live), the accumulation pattern is:

```python
tool_calls_acc = {}   # index -> {id, name, arguments_chunks}
for chunk in stream:
    for tc in (chunk.choices[0].delta.tool_calls or []):
        if tc.index not in tool_calls_acc:
            tool_calls_acc[tc.index] = {"id": tc.id, "name": "", "arguments": ""}
        if tc.function.name:
            tool_calls_acc[tc.index]["name"] += tc.function.name
        if tc.function.arguments:
            tool_calls_acc[tc.index]["arguments"] += tc.function.arguments
# After stream ends, parse JSON from tool_calls_acc[i]["arguments"]
```

Do not try to parse arguments mid-stream — wait for the stream to complete before `json.loads`.

### Error / Retry Semantics

The SDK retries automatically on 408, 429, 5xx (up to 2 times, exponential backoff). For the agent loop, catch `openai.APIError` and treat it as a terminal step with an error message — do not retry inside the loop, let the SDK handle it. Catch `openai.APITimeoutError` separately to surface "timed out" to the user. Empty `content` with `finish_reason == "stop"` and no `tool_calls` is a degenerate case — treat as terminal.

### Tool Result Injection

After executing a tool, append the result back to `messages`:

```python
messages.append(msg)   # assistant message with tool_calls
messages.append({
    "role": "tool",
    "tool_call_id": msg.tool_calls[0].id,
    "content": json.dumps(result),   # str; keep row counts, not full DataFrames
})
```

Do not embed raw DataFrames in the message list. Store DataFrames in `st.session_state` keyed by a per-turn UUID; pass only metadata (row count, columns, `data_ref` key) to the model.

---

## Streamlit Primitives for Agent Trace UX

**Confidence: HIGH** — verified against official Streamlit docs (v1.56.0 is current; no breaking changes to these primitives in 2026 releases).

### Live Step Trace

```python
with st.status("Running agent...", expanded=True) as status:
    for step in range(max_steps):
        with st.container():
            # show tool name, args, row count as they resolve
            ...
    status.update(label="Done", state="complete", expanded=False)
```

`st.status` is a mutable expander — it starts with a spinner icon (`state="running"`), collapses on completion, and supports `state="error"` for failures. It was available before Streamlit 1.40. **Use it as the outer container for the full agent trace.** Streamlit 1.53.0+ treats spinners as transient (no stale elements on rerun), and 1.55.0+ added `on_change` to expanders — both beneficial but not required.

### Streaming Final Answer

```python
with st.chat_message("assistant"):
    answer = st.write_stream(stream_generator())
st.session_state.messages.append({"role": "assistant", "content": answer})
```

`st.write_stream` accepts a generator yielding string chunks, an OpenAI `Stream` object, or any iterable. It returns the fully assembled string (or list of objects), which is safe to store in session_state for chat history. Available since Streamlit 1.31; no changes in 2026.

### Rerun Safety

Streamlit reruns the entire script on every user interaction. The agent loop must not re-execute on rerun. Pattern: store agent output in `st.session_state` before the rerun occurs. Trigger the loop only when `st.session_state.get("pending_query")` is set. Clear it immediately at loop start.

```python
if "pending_query" in st.session_state:
    query = st.session_state.pop("pending_query")
    # run loop, write to session_state.messages
```

### Per-Turn DataFrame Cache

Store DataFrames in `st.session_state` as a plain dict keyed by a per-turn UUID. This is session-scoped (single-user, not shared across users) and survives reruns within the turn.

```python
import uuid
ref = str(uuid.uuid4())
st.session_state.setdefault("df_cache", {})[ref] = df
# pass ref to model as data_ref; retrieve in make_chart tool
df = st.session_state["df_cache"][ref]
```

Per PROJECT.md, v1 is stateless per turn — clear `df_cache` at the start of each new user query. This bounds memory naturally.

---

## Recommended OpenAI Models

**Confidence: MEDIUM-HIGH** — pricing and context windows verified via CloudPrice (updated April 2026) and cross-referenced with official OpenAI model pages. Tool-call reliability claims from OpenAI's GPT-4.1 launch announcement.

| Model | Context | Max Output | Input $/1M | Output $/1M | Tool Calling | Verdict |
|-------|---------|-----------|-----------|------------|-------------|---------|
| `gpt-4.1-mini` | 1M tokens | 33K tokens | $0.40 | $1.60 | Parallel tool calls, high reliability | **Primary recommendation** |
| `gpt-4.1` | 1M tokens | 33K tokens | $2.00 | $8.00 | Parallel tool calls, highest reliability | Fallback / accuracy escalation |
| `gpt-4o` | 128K tokens | — | $2.50 | $10.00 | Parallel tool calls | Superseded; gpt-4.1-mini is cheaper and better for tool calling |
| `gpt-4o-mini` | 128K tokens | — | $0.15 | $0.60 | Yes | Cheapest, but 128K context and weaker instruction following vs gpt-4.1-mini |

### Recommendation: `gpt-4.1-mini` as primary, `gpt-4.1` as fallback

**Why gpt-4.1-mini:**
- 1M token context window is far beyond what any UFS ReAct loop will need (max ~20 turns × ~500 tokens each = ~10K tokens), but the headroom eliminates any risk of context overflow.
- 30% more efficient at tool calling than gpt-4o per OpenAI's GPT-4.1 launch announcement; excels at instruction following — critical for the structured tool arguments (`run_sql`, `pivot_to_wide`, `make_chart`).
- At $0.40/$1.60 per 1M tokens, a 5-step loop costs well under $0.01 per user query.
- Deprecation scheduled 2026-11-04 — sufficient runway for v1; plan migration to successor by Q3 2026.

**Why gpt-4.1 as fallback (not o3-mini):**
- `o3-mini` is a reasoning model; reasoning models add latency and token cost for a task (SQL generation + pivot decisions) that does not require deep chain-of-thought. Not recommended here.
- `gpt-4.1` provides maximum tool-call reliability at 5× cost — appropriate if gpt-4.1-mini produces incorrect SQL or misroutes tools in production.

**Make the model name a configurable field in `AppConfig`** (already Pydantic-typed) so operators can switch without code changes.

---

## Tool Schema Definition Pattern

**Confidence: HIGH** — verified against SDK TypedDict source and Pydantic v2 docs.

Use `Pydantic BaseModel` with `model_json_schema()`. Do not use raw `dict` literals or `TypedDict` for the `parameters` field — Pydantic gives you runtime argument validation after `json.loads` for free.

```python
from pydantic import BaseModel, Field
from typing import Literal

class RunSqlArgs(BaseModel):
    query: str = Field(description="SELECT query targeting ufs_data only")

class MakeChartArgs(BaseModel):
    chart_type: Literal["bar", "line", "scatter", "heatmap"]
    x: str
    y: str
    color: str | None = None
    title: str
    data_ref: str = Field(description="UUID key into df_cache session state")

# Usage in tool definition:
{
    "type": "function",
    "function": {
        "name": "make_chart",
        "description": "...",
        "parameters": MakeChartArgs.model_json_schema(),
    },
}

# Usage in tool dispatch:
args = MakeChartArgs.model_validate_json(tool_call.function.arguments)
```

This approach is already consistent with the project's existing Pydantic-first config pattern.

---

## Test Tooling

**Confidence: HIGH** — pattern verified against current pytest + unittest.mock docs; no new dependencies required.

### Unit Tests (per tool)

```python
from unittest.mock import MagicMock, patch
import json, pytest

def make_tool_response(name: str, arguments: dict):
    tc = MagicMock()
    tc.id = "call_abc123"
    tc.function.name = name
    tc.function.arguments = json.dumps(arguments)
    msg = MagicMock()
    msg.tool_calls = [tc]
    msg.content = None
    resp = MagicMock()
    resp.choices = [MagicMock(message=msg, finish_reason="tool_calls")]
    return resp

def make_text_response(content: str):
    msg = MagicMock()
    msg.tool_calls = None
    msg.content = content
    resp = MagicMock()
    resp.choices = [MagicMock(message=msg, finish_reason="stop")]
    return resp
```

### Integration Test (ReAct loop)

```python
def test_react_loop_run_sql_then_answer(mock_db_adapter):
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        make_tool_response("run_sql", {"query": "SELECT * FROM ufs_data LIMIT 10"}),
        make_text_response("The answer is 42."),
    ]
    result = run_agent("test question", client=mock_client, db=mock_db_adapter)
    assert result.answer == "The answer is 42."
    assert mock_client.chat.completions.create.call_count == 2
```

Use `side_effect` as a list to sequence multiple responses across loop iterations — this is the idiomatic pytest pattern for multi-turn agent testing.

**Do not use `openai-responses` (v0.13.1, maintenance mode)** — the overhead of intercepting HTTP is not needed when you can inject `mock_client` directly via dependency injection.

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| LangChain / LangGraph | Explicitly out of scope (PROJECT.md). ~200 LOC raw loop has zero framework overhead and full control over streaming + budget enforcement. | Raw `chat.completions` loop |
| OpenAI Agents SDK | Explicitly out of scope. Adds abstraction over the very streaming/tool primitives you need to control for Streamlit integration. | Raw `chat.completions` loop |
| Pydantic AI | A framework for agents — same category as OpenAI Agents SDK. Adds a dependency and abstraction for a pattern that's ~200 LOC without it. | `Pydantic BaseModel.model_json_schema()` for schema generation only |
| `openai-responses` pytest plugin | Maintenance mode (v0.13.1, Dec 2025); mocks at HTTP layer (unnecessary complexity); no evident tool_calls mocking docs. | `unittest.mock.MagicMock` with helper constructors |
| `parallel_tool_calls=True` (default) | In a sequential ReAct loop, parallel calls complicate `max_steps` accounting and argument accumulation. The UFS tools have ordering dependencies (run_sql → pivot_to_wide → make_chart). | `parallel_tool_calls=False` explicitly |
| Streaming for tool-call turns | Streaming arguments across chunks requires index-based accumulation logic with no UX benefit (JSON args are not human-readable). | Non-streaming for tool turns; streaming only for final text answer |
| `gpt-4o` / `gpt-4o-mini` as primary | gpt-4.1-mini supersedes both for this use case: better tool-call reliability than gpt-4o-mini, 1M context window vs 128K, and cheaper than gpt-4o. | `gpt-4.1-mini` |
| `o3-mini` | Reasoning model; adds latency and token cost for SQL generation which does not benefit from deep chain-of-thought. | `gpt-4.1-mini` |

---

## Installation

No new packages required. All capabilities are in the existing `requirements.txt`:

```
openai>=1.50        # tool calling, streaming, retry, APITimeoutError
streamlit>=1.40     # st.status, st.write_stream, st.chat_message, session_state
pydantic>=2.7       # model_json_schema(), model_validate_json()
pandas>=2.2         # pivot_table for pivot_to_wide tool
plotly>=5.22        # make_chart tool (bar/line/scatter/heatmap)
```

`httpx` is a transitive dependency of `openai` — no explicit pin needed.

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `openai>=1.50` | `httpx>=0.23` (transitive) | `httpx.Timeout` is the recommended way to set per-request timeouts in SDK 1.x. No `request_timeout` kwarg — use `timeout=httpx.Timeout(30.0)` in `.create()`. |
| `streamlit>=1.40` | All primitives above | `st.status` and `st.write_stream` both predate 1.40. 1.53.0+ improves spinner transience; 1.55.0+ adds expander `on_change` — nice-to-have but not required. |
| `pydantic>=2.7` | `openai>=1.50` | OpenAI SDK uses Pydantic v2 internally; `model_json_schema()` is the v2 API (not v1's `.schema()`). |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not Alternative |
|----------|-------------|-------------|---------------------|
| Agent framework | Raw `openai` SDK loop | LangGraph, LangChain, OpenAI Agents SDK | Explicitly out of scope; ~200 LOC raw loop gives full control over streaming and budget; no new dependencies |
| Tool schema definition | Pydantic `model_json_schema()` | Hand-written dict / TypedDict | Pydantic schema stays in sync with runtime validation; already the project's convention |
| Primary model | `gpt-4.1-mini` | `gpt-4o-mini` | gpt-4.1-mini has better tool-call reliability, 1M vs 128K context, similar price tier |
| Primary model | `gpt-4.1-mini` | `gpt-4.1` | gpt-4.1 is 5× more expensive; reserve as escalation path for accuracy failures |
| Streaming strategy | Non-stream for tool turns; stream for final answer | Stream all turns | Tool argument JSON streaming has no UX value; accumulation logic adds complexity with no benefit |
| Pytest mocking | `unittest.mock.MagicMock` | `openai-responses` plugin | Plugin is maintenance-mode; injecting mock client directly is simpler and framework-free |

---

## Sources

- Streamlit official docs (v1.56.0) — `st.status`, `st.write_stream` API signatures and behavior verified
- Streamlit 2026 release notes — confirmed no breaking changes to streaming/status/expander primitives
- DeepWiki openai/openai-python (indexed 2026-01-12) — `ChatCompletionToolParam` TypedDict shape, `parallel_tool_calls` parameter, retry semantics
- CloudPrice.net GPT-4.1 / GPT-4.1-mini (April 2026) — context windows (1M), max output (33K), pricing ($2/$8 and $0.40/$1.60 per 1M tokens), parallel function calling support confirmed
- OpenAI community: parallel_tool_calls default behavior — default is `True` in SDK despite some doc inconsistency; explicit `False` for sequential loop confirmed
- OpenAI community: streaming tool call accumulation pattern — index-based dict accumulation with post-stream JSON parse is the canonical approach
- dev.to / nebulagg: pytest tool call mocking pattern — `MagicMock` helper constructors for non-streaming tool_calls response structure
- openai-responses PyPI — v0.13.1, maintenance mode; noted as not recommended
- GPT-4.1 launch announcement (openai.com/index/gpt-4-1/) — 30% efficiency improvement in tool calling vs gpt-4o, instruction following improvements confirmed (MEDIUM confidence — marketing claim, not independently benchmarked)

---
*Stack research for: Agentic ReAct loop on Streamlit internal data platform*
*Researched: 2026-04-22*
