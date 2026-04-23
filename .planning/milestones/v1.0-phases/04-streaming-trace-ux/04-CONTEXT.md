---
name: Phase 4 Streaming + Trace UX Context
description: Home page rewrite driving run_agent_turn with st.status live trace + st.write_stream final answer + st.expander collapse + inline Plotly. Old pending_sql flow deleted. Non-OpenAI LLM chat input disabled. Explorer/Compare/Settings unchanged.
phase: 4
status: ready_for_planning
mode: locked_requirements_skip
---

# Phase 4: Streaming + Trace UX - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning
**Mode:** Smart discuss skipped — every UX decision is locked by REQUIREMENTS.md (UX-01..07, HOME-01..04, SAFE-06). Phase 1-3 outputs (AgentConfig, AgentContext, TOOL_REGISTRY, run_agent_turn, AgentStep) are all in place.

<domain>
## Phase Boundary

`app/pages/home.py` is rewritten to consume the `run_agent_turn` event stream with full live trace UX and the old one-shot `pending_sql` flow is fully deleted.

**In-scope deliverables:**
- Rewrite `app/pages/home.py` so `st.chat_input` submits directly to `run_agent_turn(user_message, ctx)` (no preview/edit/confirm step). (HOME-01, HOME-02)
- Live trace UX inside `st.status("Thinking...", expanded=True)` — each AgentStep event renders as a line as it streams:
  - Tool call: `🛠 <tool_name>(...)` (args summarized, no raw JSON dump)
  - SQL (when tool_name == "run_sql"): `st.code(sql, language="sql")` inside the status
  - Tool result: `✓ rows=<N>` or the tool's summary content first line
  - Errors: human-readable error lines, NOT raw tracebacks (UX-07)
- After `budget_exhausted` or timeout: visible human-readable note in final answer (e.g., `"*Stopped after 5 steps; here's what I found.*"`) per UX-06.
- Final assistant text streamed via `st.write_stream(...)` into `st.chat_message("assistant")`. (UX-04)
- After final answer renders, wrap the full trace into `st.expander("Show reasoning", expanded=False)`. (UX-03)
- Inline Plotly chart from `make_chart` tool — `st.plotly_chart(fig, use_container_width=True)`. (UX-05)
- SAFE-06: If the selected LLM is not OpenAI, disable `st.chat_input` with a friendly redirect message pointing to Settings. No agent loop runs.
- Preserve existing Home UI elements unchanged: metric cards (등록된 DB, 등록된 LLM, 현재 DB), chat history render loop, "🧹 대화 초기화" button, "최근 질의" panel. (HOME-03)
- `append_chat` / `get_chat_history` store ONLY user message + final answer per turn; full traces live in a separate `_AGENT_TRACE_KEY = "agent_trace_v1"` session slot keyed by turn index. (HOME-04)
- Explorer / Compare / Settings pages remain unchanged — verified by smoke loading each. (HOME-05, deferred to Phase 5 for ship validation but no code changes here.)

**Out of scope for Phase 4:**
- Ship-bar E2E validation on seeded DB — Phase 5.
- Backfilling tests for the old Home flow (deletion is total).
- Modifying Explorer/Compare/Settings code — they stay untouched; this phase must not break them.

</domain>

<decisions>
## Implementation Decisions

### Locked by REQUIREMENTS.md (not negotiable)
- **st.status + live trace (UX-01):** Use `st.status(label, expanded=True)` as the outer container. Each AgentStep calls `status.write(...)` or appends rendered elements. Label updates as steps progress (`"Thinking..."` → `"Running SQL..."` → `"Building chart..."`).
- **st.code for SQL (UX-02):** When step.tool_name == "run_sql" AND step.sql is not None: `st.code(step.sql, language="sql")` inside the current status container.
- **st.expander collapse after final (UX-03):** After the final-answer AgentStep renders, replace/wrap the trace into `st.expander("Show reasoning", expanded=False)`. Implementation detail: render the trace INSIDE an expander from the start (expanded=True initially, then re-rendered expanded=False after completion via a session-state flag) OR buffer steps and render the expander once at the end. Claude's Discretion — the more reliable Streamlit pattern is buffer-then-render.
- **st.write_stream for final text (UX-04):** `st.write_stream(<generator yielding text chunks>)`. Phase 3's `run_agent_turn` yields a complete final-answer AgentStep (not a chunk stream). For UX-04 compliance, Phase 4 wraps the final answer text in a simple chunk generator (split by whitespace or char-by-char with small delays) so `st.write_stream` produces a progressive reveal — or requests a streaming final call from the loop. Prefer the text-chunk wrapper: `def _stream_text(s): for c in s: yield c; time.sleep(0.005)` — zero new loop API surface.
- **st.plotly_chart inline (UX-05):** `st.plotly_chart(step.chart, use_container_width=True)` for any step with step.chart is not None. Rendered inside the status container as it streams.
- **Budget note (UX-06):** Phase 3 flags `AgentStep.budget_exhausted=True` on forced-finalization. Home appends the prefix `"*Stopped after {max_steps} steps; here's what I found.*\n\n"` (or timeout variant) to the streamed text when this flag is set.
- **Tool errors as human-readable (UX-07):** `step.error` (if set) or `step.content` (for ToolResult errors) renders as a plain text line — NO traceback. Phase 3 already normalizes tool exceptions to `ToolResult(content="<error text>")` so this is mostly automatic.
- **Direct submit (HOME-01):** No preview textarea. `st.chat_input("...", disabled=<not OpenAI>)` → when submitted, immediately runs the loop.
- **Old flow deletion (HOME-02):** Remove from home.py: `pending_sql` session-state reads/writes, Execute/Discard buttons, `extract_sql_from_response` call, direct `auto_chart(df)` call. Grep-verifiable post-phase.
- **Preserved Home elements (HOME-03):** Keep: `show_metric_cards()`-like function, the chat-history iteration block, the `🧹 대화 초기화` button handler, the `최근 질의` recent-queries panel. These must KEEP WORKING unchanged.
- **Chat history shape (HOME-04):** `append_chat(user_msg, assistant_msg)` continues to accept the final answer text as `assistant_msg`. Traces go to `st.session_state[_AGENT_TRACE_KEY][turn_index]: list[AgentStep]` — keyed by 0-indexed turn.
- **SAFE-06 disable:** If the resolved LLM adapter class name is not `OpenAIAdapter`, render `st.info("AI Q&A uses OpenAI only in v1 — switch your LLM to an OpenAI entry in Settings.")` AND pass `disabled=True` to `st.chat_input`.
- **No changes to Explorer/Compare/Settings:** Grep assertion `git diff` shows zero changes in those files.

### Conventions
- Korean docstring + Korean user-facing messages where the existing home.py uses Korean (matches current style).
- `from __future__ import annotations` at module top.
- Import `run_agent_turn`, `AgentStep` from `app.core.agent` (the lazy re-export established in Phase 3).
- Session-state keys namespaced: `_AGENT_TRACE_KEY = "agent_trace_v1"` (exact string from Phase 1's SESSION-AUDIT.md).

### Claude's Discretion (implementation details not covered by requirements)
- **Expander render pattern:** Buffer steps during live streaming into a list; render them inside `st.status` while the loop is running; after the loop finishes, within `st.expander("Show reasoning", expanded=False)` re-render the same list. Two renders — acceptable for a reasonable trace length (max_steps=5 → small volume).
- **Step label for status container:** Updates can be static (`"Thinking..."` throughout) or dynamic based on current step. Prefer dynamic for better UX.
- **Chart placement:** When a `make_chart` step yields a chart, render inline within the status (during streaming) AND also include it in the final chat_message block (after the expander collapses). Avoids the chart disappearing when the expander collapses. Phase 4 may render once per turn at the END of the main chat_message block to keep it simple.
- **Text-chunk generator for st.write_stream:** Simple char-by-char with tiny sleep. Alternative: split by space for word-level streaming. Prefer word-level (less flicker, still feels live).
- **"Thinking..." while waiting for first create():** `st.status` with `expanded=True` is visible immediately; no separate spinner needed.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/core/agent::run_agent_turn(user_message, ctx) -> Iterator[AgentStep]` — Phase 3 output; the main consumer API.
- `app/core/agent::AgentStep` — dataclass with step_type, tool_name, tool_args, sql, df_ref, chart, content, error, budget_exhausted, duration_ms, step_index.
- `app/core/agent/config.py::AgentConfig` — read via `ctx.config.agent` for budgets to display in UX-06 notes.
- `app/core/session.py` — existing session_state helpers (append_chat, get_chat_history, recent queries). Already has chat_history and recent_queries keys.
- `app/core/runtime.py::resolve_selected_db`, `resolve_selected_llm` — existing resolvers for current DB/LLM selection.
- `app/core/auth.py::require_login` — existing auth gate.
- `app/utils/viz.py::auto_chart` — DEPRECATED in Phase 4 (remove from home.py imports). make_chart tool replaces it for the agent path. Do NOT delete from utils/ since other pages (Explorer) may use it.

### Existing Home page structure (before rewrite)
- `app/pages/home.py` — reads `pending_sql` from session_state, shows a preview textarea, Execute button runs SQL via adapter, calls `auto_chart(df)` on result. This entire flow is DELETED.
- Preserved: metric cards, chat history list render, 대화 초기화 button, 최근 질의 panel.
- Login guard at top, sidebar DB/LLM selectors (continue to work).

### Integration Points
- `app/pages/home.py` — MAJOR rewrite (most of file).
- `app/core/session.py` — MAY add `_AGENT_TRACE_KEY` constant + helpers (`append_agent_trace`, `get_agent_trace`). Claude's Discretion — can live inline in home.py or be promoted to session.py. Prefer session.py to keep home.py lean.
- No changes expected to adapters, config, core/agent, tools, logger.

### Dependencies
- Streamlit 1.40+ (already pinned). No new deps.

</code_context>

<specifics>
## Specific Ideas

- **AgentContext construction for each turn:**
  ```python
  ctx = AgentContext(
      db_adapter=db, llm_adapter=llm, config=cfg,
      user=st.session_state.get("user", "anonymous"),
  )
  # Loop sets ctx.current_tool_call_id internally before each tool dispatch
  ```

- **Step rendering switch** (inside `st.status`):
  ```python
  if step.step_type == "tool_call":
      status.write(f"🛠 **{step.tool_name}**(...)")
      if step.tool_name == "run_sql" and step.sql:
          status.code(step.sql, language="sql")
  elif step.step_type == "tool_result":
      first = (step.content or "").splitlines()[0][:120]
      status.write(f"✓ {first}")
      if step.chart is not None:
          status.plotly_chart(step.chart, use_container_width=True)
  elif step.step_type == "final_answer":
      final_text = step.content or ""
      if step.budget_exhausted:
          final_text = f"*Stopped after {cfg.agent.max_steps} steps; here's what I found.*\n\n" + final_text
      # Render OUTSIDE the status via st.write_stream on a chunk generator
  ```

- **Non-OpenAI guard (SAFE-06):**
  ```python
  is_openai = llm_adapter.__class__.__name__ == "OpenAIAdapter"
  if not is_openai:
      st.info("이 Q&A는 v1에서 OpenAI 전용입니다 — Settings에서 OpenAI LLM을 선택하세요.")
  user_msg = st.chat_input("질문을 입력하세요...", disabled=not is_openai)
  ```

- **Trace persistence:**
  ```python
  _AGENT_TRACE_KEY = "agent_trace_v1"
  traces = st.session_state.setdefault(_AGENT_TRACE_KEY, {})
  traces[turn_index] = list_of_steps_this_turn
  ```

- **Rendering past turns' traces:** When iterating chat_history for render, also fetch `traces[turn_index]` and render into `st.expander("Show reasoning", expanded=False)` below the assistant message. Keeps the UX consistent across reruns.

- **File structure:** Single `app/pages/home.py` file. All Phase 4 code lives in there. Optional helper `app/pages/_home_helpers.py` if the file grows large, but prefer to keep inline.

- **Manual smoke test (for post-exec verification, not automated):**
  1. `streamlit run app/main.py` launches without errors.
  2. Home page loads without traceback.
  3. Selecting a non-OpenAI LLM disables chat_input.
  4. Selecting an OpenAI LLM enables chat_input.
  5. Explorer, Compare, Settings pages still load and their UIs are unchanged.
  6. End-to-end agent run is a Phase 5 ship-bar scenario — NOT required to pass in Phase 4 (may fail due to spec scaffold text or live DB absence).

</specifics>

<deferred>
## Deferred Ideas

- **Cancel button for in-flight turn** — UXEX-01 v2.
- **Confidence signal badge** — UXEX-02 v2.
- **Cross-turn memory** — MEM-01/MEM-02 v2.
- **True LLM token streaming (vs chunk wrapper)** — not requested; stream=True on the final finalization call is a Phase 5 polish option.

</deferred>
