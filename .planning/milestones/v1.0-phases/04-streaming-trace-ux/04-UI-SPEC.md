---
phase: 04-streaming-trace-ux
type: ui-spec
status: locked
mode: requirements_derived
---

# Phase 4: Home Page Agentic UX — Design Contract

## Layout

```
┌─────────────────────────────────────────────────────────┐
│ Sidebar: DB/LLM selectors (existing, unchanged)         │
├─────────────────────────────────────────────────────────┤
│ Header: "🏠 AI Data Chat" (existing Korean label ok)    │
│                                                          │
│ ┌──── Metric Cards (existing) ────┐                     │
│ │ 등록된 DB │ 등록된 LLM │ 현재 DB │                     │
│ └──────────────────────────────────┘                     │
│                                                          │
│ [Non-OpenAI guard banner if applicable — st.info]       │
│                                                          │
│ ── Chat transcript (st.chat_message blocks) ──          │
│  [user] "Compare wb_enable across devices"              │
│  [assistant]                                            │
│    (streamed text via st.write_stream)                  │
│    [st.plotly_chart if chart emitted]                   │
│    ▸ Show reasoning (st.expander, collapsed)            │
│       └─ 🛠 run_sql(...)                               │
│          ```sql                                         │
│          SELECT ...                                     │
│          ```                                            │
│          ✓ rows=42                                      │
│       └─ 🛠 pivot_to_wide(...)                         │
│          ✓ df_ref=call_abc:wide                         │
│       └─ 🛠 make_chart(bar)                            │
│          [chart thumbnail inline]                       │
│                                                          │
│ [While streaming: st.status("Thinking…", expanded=True) │
│  with each step appended as it arrives]                 │
│                                                          │
│ ── Chat input ──                                        │
│  st.chat_input("질문을 입력하세요...",                    │
│                disabled=<not OpenAI>)                   │
│                                                          │
│ [existing 🧹 대화 초기화 button]                         │
│ [existing 최근 질의 panel]                              │
└─────────────────────────────────────────────────────────┘
```

## Interaction Flow

### Happy path (OpenAI selected, question submitted)
1. User types a question in `st.chat_input` and hits Enter.
2. User message appears in `st.chat_message("user")`.
3. Below it, `st.status("Thinking...", expanded=True)` opens.
4. Script calls `run_agent_turn(user_message, ctx)` — consumes the AgentStep generator.
5. For each step:
   - `tool_call` → status: `🛠 <tool>(...)`. If `tool_name == "run_sql"`: also `status.code(step.sql, language="sql")`.
   - `tool_result` → status: `✓ <first line of content>`. If `step.chart`: `status.plotly_chart(..., use_container_width=True)`.
   - Status label updates ("Running SQL...", "Building chart...").
6. When `final_answer` step arrives:
   - Status closes (complete).
   - Text flows through `st.write_stream(_stream_text(step.content))` into `st.chat_message("assistant")`.
   - If `step.budget_exhausted`: text is prefixed `"*Stopped after 5 steps; here's what I found.*\n\n"`.
   - If any step had a chart: render `st.plotly_chart(chart, use_container_width=True)` below the streamed text.
   - Trace collapses into `st.expander("Show reasoning", expanded=False)` below the chart.
7. `append_chat(user_msg, final_text)` persists. `traces[turn_index] = steps` persists to `st.session_state[_AGENT_TRACE_KEY]`.
8. `st.rerun()` (Streamlit convention) to render the new persisted transcript line with the collapsed expander on subsequent renders.

### Non-OpenAI path (SAFE-06)
1. LLM adapter is not `OpenAIAdapter`.
2. Render `st.info("이 Q&A는 v1에서 OpenAI 전용입니다 — Settings에서 OpenAI LLM을 선택하세요.")`.
3. `st.chat_input(..., disabled=True)`.
4. No loop is ever invoked.

### Error path (tool failure, UX-07)
- Tool raises → Phase 3 catches, emits `AgentStep(step_type="tool_result", content="tool error: <msg>", error="<msg>")`.
- Home renders: `status.write(f"⚠ {step.content}")` — plain text, NO traceback.
- Loop continues with error fed back to model.

## Component Choices (grep-verifiable)

| Element | Component | Req |
|---|---|---|
| Outer trace container | `st.status("...", expanded=True)` | UX-01 |
| SQL rendering | `st.code(sql, language="sql")` | UX-02 |
| Post-final collapse | `st.expander("Show reasoning", expanded=False)` | UX-03 |
| Streamed final text | `st.write_stream(...)` | UX-04 |
| Chart | `st.plotly_chart(fig, use_container_width=True)` | UX-05 |
| Budget note prefix | literal `*Stopped after N steps; here's what I found.*` | UX-06 |
| Tool-error line | plain `status.write(...)` (no st.exception, no st.error) | UX-07 |
| Chat input | `st.chat_input(..., disabled=<bool>)` | HOME-01, SAFE-06 |

## Accessibility & Copy

- All labels continue in Korean for user-facing text ("질문을 입력하세요", "대화 초기화", "최근 질의").
- Status label updates are short English-equivalents of the tool being dispatched (acceptable mix — model responses will be in the user's question language).
- Expander label `"Show reasoning"` is fine in English (matches UX-03 literal).

## Out of scope for this UI contract

- Brand colors, typography, dark mode — Streamlit default theme; no custom CSS.
- Keyboard shortcuts beyond Enter-to-submit (Streamlit default).
- Screen-reader ARIA labels — Streamlit components handle this.
- Responsive/mobile layout — existing app already uses Streamlit's responsive defaults.
