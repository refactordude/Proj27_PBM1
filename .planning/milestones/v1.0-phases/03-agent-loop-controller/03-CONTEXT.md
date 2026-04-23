---
name: Phase 3 Agent Loop Controller Context
description: run_agent_turn() ReAct loop over OpenAI tool-calling with strict budget enforcement (max_steps, timeout, max_context_tokens) + forced finalization. All behavioral specifics locked by REQUIREMENTS.md AGENT-01..AGENT-06 — minimal grey area.
phase: 3
status: ready_for_planning
mode: locked_requirements_skip
---

# Phase 3: Agent Loop Controller - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning
**Mode:** Smart discuss skipped — every control-flow decision is locked by REQUIREMENTS.md (AGENT-01..06, OBS-02, TEST-02, TEST-03, TEST-05). Phase 1 contracts + Phase 2 TOOL_REGISTRY are both in place.

<domain>
## Phase Boundary

`run_agent_turn(user_message) -> Iterator[AgentStep]` is fully implemented, enforces all budget constraints, and is verified by integration tests with a mocked OpenAI client — so the loop is proven correct before any Streamlit code touches it.

**In-scope deliverables (by REQUIREMENTS.md):**

- `AgentStep` dataclass/Pydantic model — typed event yielded by the loop. Fields surface the step type (tool_call, tool_result, final_answer, budget_exhausted), tool_name, arguments, content, chart, sql (if applicable), duration_ms. (AGENT-02)
- `run_agent_turn(user_message: str, ctx: AgentContext) -> Iterator[AgentStep]` — the ReAct loop using OpenAI `chat.completions.create` with `tools=[<TOOL_REGISTRY schemas>]`, `tool_choice="auto"`, `parallel_tool_calls=False` on every call. (AGENT-01)
- Loop termination on final assistant message with no tool calls → yields final-answer `AgentStep`. (AGENT-02)
- `max_steps=5` counted per tool call (NOT per response). Loop halts further tool dispatch at the cap. (AGENT-03)
- When `max_steps` reached without final answer: one forced-finalization call with `tool_choice="none"`; returns its text as the final answer. (AGENT-04)
- Wall-clock `timeout_s=30` per user turn (soft — in-flight finalization allowed to complete). (AGENT-05)
- `max_context_tokens=30000` cumulative tool-result token usage tracker → triggers forced finalization if exceeded. (AGENT-06)
- Every LLM call logs to `logs/llm.log` via `log_llm()` with user, model, step index, question (first step only), duration, tool-call names emitted, error. (OBS-02)
- Three integration tests using `unittest.mock.MagicMock` with `side_effect=[...]`:
  - `test_react_loop_run_sql_then_answer` — 2-step loop asserting AgentStep sequence + create() called exactly twice. (TEST-02)
  - `test_forced_finalization_on_budget_exhaustion` — 5 tool-call responses + forced finalization, asserts final text-only AgentStep. (TEST-03)
  - Plus `test_max_context_tokens_triggers_finalization` per SC5.
- Test discipline: assertions are on argument shape, tool-dispatch order, and loop-control semantics — NOT on specific model-emitted SQL strings. (TEST-05)

**Out of scope for Phase 3:**
- Streamlit UI rendering / `st.status` / `st.write_stream` — Phase 4.
- Home page rewrite (HOME-01..04) — Phase 4.
- Ship-bar E2E validation — Phase 5.
- Any modification to tool code (run_sql, get_schema, etc.) — Phase 2 is frozen.

</domain>

<decisions>
## Implementation Decisions

### Locked by REQUIREMENTS.md (not negotiable)
- **Parallel tool calls OFF:** `parallel_tool_calls=False` on EVERY `chat.completions.create` call — not just the first one. Prevents Pitfall 2 (budget accounting breakage + ordering violations). Grep-verifiable on `loop.py`.
- **Forced finalization semantics (AGENT-04):** When `max_steps` is hit, issue exactly ONE more call with `tool_choice="none"` and `tools=[...]` still attached (the model won't emit tool_calls because tool_choice forbids it). Yield the returned text as a final `AgentStep`. The user-visible note (UX-06 in Phase 4) is prefixed at display time — Phase 3 stores the raw text + a `budget_exhausted=True` flag on the step.
- **Step counting (AGENT-03):** Increment the counter when a tool call is dispatched, not per response. A response with 2 tool_calls (shouldn't happen with parallel_tool_calls=False, but safety net) increments by 2.
- **Timeout semantics (AGENT-05):** Measured with `time.monotonic()` at turn start. Checked before each `chat.completions.create` call — if elapsed ≥ 30s and no final answer yet, issue forced finalization immediately. The finalization call itself is allowed to complete even if its round-trip exceeds 30s (soft timeout).
- **Token accounting (AGENT-06):** Sum `usage.completion_tokens + usage.prompt_tokens` from each response.usage, plus an approximate token count for tool results (use `len(content.encode('utf-8')) // 4` as a char-per-token heuristic OR use `tiktoken` if in venv; otherwise char/4 is acceptable per research). If cumulative > 30000, force finalization.
- **Stateless per turn (AGENT-07 from Phase 1):** Every call to `run_agent_turn` creates a FRESH `AgentContext`. No DataFrame, tool-result, or `result_N` reference survives across turns. Phase 1's `AgentContext` already enforces this via `field(default_factory=dict)`.
- **Timeout on every create() (AGENT-08 from Phase 1):** Already wired in Phase 1 openai_adapter.py, but the loop makes calls OUTSIDE that adapter — the loop MUST also pass `timeout=httpx.Timeout(30.0)` (or the loop-level equivalent) on every raw OpenAI SDK call. Reuse the `_REQUEST_TIMEOUT` constant or re-import `httpx.Timeout(30.0)`.
- **Logging (OBS-02):** `log_llm()` called ONCE per `chat.completions.create` round-trip. Fields: user (from ctx.user), model (from ctx.config.agent.model), step_index (loop counter), question (ctx.user_message on step 0 only, else ""), duration_ms, tool_call_names (comma-joined if any, empty if none), error (None or str).

### Conventions (follow existing patterns)
- `from __future__ import annotations` on every new module.
- Korean module docstring (short) per CLAUDE.md.
- File layout: `app/core/agent/loop.py` (main module — `run_agent_turn`, `AgentStep`, internal helpers). All loop concerns in one file — no `loop/` subpackage.
- Tests: `tests/core/agent/test_loop.py` for the integration tests per TEST-02/TEST-03/TEST-05. stdlib `unittest` + `unittest.mock.MagicMock`.
- Tool dispatch via `TOOL_REGISTRY[tool_name](ctx, args)` — the loop never imports specific tools. Reading `args` = `tool.args_model.model_validate_json(raw_args_str)` (OpenAI returns a JSON string).
- Errors from tools become `ToolResult(content="<error>")` (Phase 2 contract) — loop feeds the error content back to the model as the tool_call message. Loop never raises on a tool failure unless it's a framework-level bug.

### Claude's Discretion (implementation details not covered by requirements)
- **`AgentStep` form:** dataclass vs Pydantic. Prefer dataclass (consistent with AgentContext; avoids Pydantic arbitrary_types hassle for the Plotly figure).
- **Step variants:** a single dataclass with optional fields vs a discriminated union. Prefer single dataclass with a `step_type: Literal[...]` field — simpler to yield; Phase 4's UI code branches on step_type.
- **Token counting heuristic:** char/4 for tool-result content estimation. If `tiktoken` ends up in the venv, prefer it. Research recommended char/4.
- **Error envelope to model on tool dispatch failure (e.g. Pydantic ValidationError on args):** feed back as `{"role": "tool", "tool_call_id": <id>, "content": f"tool argument error: {e}"}` — lets the model retry within the step budget.
- **Streamlit agnosticism (SC4):** Zero `streamlit` imports in `loop.py`. The loop is pure Python. Any UI-specific helpers (e.g., formatting a step for st.status display) live in Phase 4's `home.py`, NOT here.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets (from Phase 1 + Phase 2)
- `app/core/agent/config.py::AgentConfig` — `max_steps`, `row_cap`, `timeout_s`, `max_context_tokens`, `model` all present with correct defaults.
- `app/core/agent/context.py::AgentContext` — `db_adapter`, `llm_adapter`, `config`, `user`, `_df_cache`, `current_tool_call_id`. Loop sets `current_tool_call_id` before dispatching a tool so pivot_to_wide/normalize_result can key their cache writes.
- `app/core/agent/tools::TOOL_REGISTRY` — `dict[str, Tool]` with all 6 tools. Loop iterates `TOOL_REGISTRY[name]`.
- Each `Tool.args_model.model_json_schema()` → OpenAI tool schema. The loop builds the `tools=[...]` parameter once at turn start: `[{"type": "function", "function": {"name": t.name, "description": <tool.description or ""> , "parameters": t.args_model.model_json_schema()}} for t in TOOL_REGISTRY.values()]`.
- `app/core/logger.py::log_llm(*, user, model, step_index, question, duration_ms, tool_call_names, error)` — existing JSONL logger.
- `app/adapters/llm/openai_adapter.py` — has `_REQUEST_TIMEOUT = httpx.Timeout(30.0)` at module scope. Loop can import and reuse.

### Established Patterns
- Pure Python modules with narrow surface (one public function per module is common).
- stdlib unittest + MagicMock; no pytest dependency.
- Adapter-agnostic: the loop should work with any OpenAI-compatible client that exposes `chat.completions.create`. Do NOT hard-code `openai.OpenAI(...)` — accept the client from `ctx.llm_adapter._client()` (OpenAIAdapter exposes this).

### Integration Points
- `app/core/agent/loop.py` — NEW: `run_agent_turn`, `AgentStep`, internal helpers.
- `app/core/agent/__init__.py` — CURRENTLY EMPTY (Phase 1 left it so). Phase 3 can optionally re-export `run_agent_turn` here for a clean import (`from app.core.agent import run_agent_turn`). Claude's Discretion — Phase 4 will use this entry point.
- NO changes to `app/core/agent/tools/` — Phase 2 frozen.
- NO Streamlit imports anywhere in this phase.

### Dependencies
- `openai>=1.50` (pinned), `httpx>=0.27` (explicit from Phase 1), `pandas` (transitive via pd.DataFrame in AgentStep.chart or .content). No new pip deps.

</code_context>

<specifics>
## Specific Ideas

- **`AgentStep` fields (minimal set):**
  - `step_type: Literal["tool_call", "tool_result", "final_answer", "budget_exhausted"]`
  - `step_index: int` — loop counter
  - `tool_name: str | None` — set for tool_call / tool_result
  - `tool_args: dict | None` — JSON-parsed args (for audit trail in the UI trace)
  - `content: str` — for tool_result (the ToolResult.content) OR final_answer text
  - `sql: str | None` — set only if tool_name == "run_sql" (UI renders in st.code)
  - `df_ref: str | None` — passed through from ToolResult (helps downstream tools)
  - `chart: Any | None` — Plotly Figure from make_chart (pandas allowed)
  - `duration_ms: int | None` — per-step wall-clock
  - `error: str | None`
  - `budget_exhausted: bool = False` — set on the forced-finalization final answer

- **Loop skeleton (Claude's Discretion on exact structure):**
  1. Build `tools=[...]` schema list once from TOOL_REGISTRY.
  2. Initialize `messages = [{"role": "system", ...}, {"role": "user", "content": user_message}]`.
  3. Loop while True:
     - Check timeout / step budget / token budget.
     - If exhausted → issue forced-finalization call (tool_choice="none"), yield final-answer step with budget_exhausted=True, break.
     - Call `chat.completions.create(model, messages, tools, tool_choice="auto", parallel_tool_calls=False, timeout=_REQUEST_TIMEOUT)`.
     - Log via `log_llm()`.
     - If response has tool_calls: for each (respecting parallel_tool_calls=False there should be ≤1, but loop is safe for >1), set ctx.current_tool_call_id, dispatch via TOOL_REGISTRY, yield tool_call + tool_result AgentSteps, append tool role message with `content=ToolResult.content`, `tool_call_id=<id>`, increment step counter per tool call, accumulate token count from usage.
     - Else (no tool_calls): yield final-answer step with response.choices[0].message.content, break.

- **System prompt content:** Short — tell the model it's a UFS database assistant with these tools; encourage use of get_schema first for orientation; emphasize concise final answers. The exact prompt text is Claude's Discretion; Phase 5 may tune it.

- **`get_schema_docs.description` / etc. for OpenAI `tools=[]`:** Each tool's `args_model` JSON schema already has field descriptions. The tool-level `description` (model-facing instruction) isn't on the tool today — the loop supplies it from a small dict keyed by tool name (literal text, Claude's Discretion; Phase 5 may tune). Plan should create a small `_TOOL_DESCRIPTIONS: dict[str, str]` in loop.py.

</specifics>

<deferred>
## Deferred Ideas

- **Streaming the final answer text (stream=True)** — out of scope for Phase 3 (the LOOP mechanics). Phase 4 handles UI streaming; it can wrap the final-answer call with `stream=True` when Phase 4 calls a dedicated streaming helper. For Phase 3 integration tests a non-streaming final call is simpler to assert against.
- **Tool call retries with back-off** — out of scope; model handles retry within step budget.
- **Cost / usage tracking** — HARD-06 v2 backlog.
- **Cancel button for in-flight turn** — UXEX-01 v2 backlog.

</deferred>
