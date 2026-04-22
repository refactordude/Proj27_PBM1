---
phase: 04-streaming-trace-ux
reviewed: 2026-04-22T22:10:57Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - app/pages/home.py
  - app/core/session.py
  - tests/core/test_session_agent_trace.py
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-04-22T22:10:57Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

The Phase 4 streaming-trace UX implementation in `app/pages/home.py` is largely consistent with `04-UI-SPEC.md`. The agentic flow drives `run_agent_turn` directly, renders AgentStep events live inside `st.status(expanded=True)`, streams the final answer via `st.write_stream`, and collapses the trace into `st.expander(..., expanded=False)`. SAFE-06 (non-OpenAI chat_input lock) is in place, old-flow helpers (`pending_sql`, `extract_sql_from_response`, `auto_chart`) are no longer imported or called from `home.py`, and the `_AGENT_TRACE_KEY` session helpers are correctly scoped.

However, three warnings were identified that affect correctness and user experience:
1. The inline chart rendered under the streamed final answer is not preserved across Streamlit reruns — the post-rerun transcript only shows the chart buried inside the collapsed expander (UX regression vs. live turn).
2. The `final_answer` branch in `_render_step_live` never handles the `error`-bearing forced-finalization case for non-error cases — if the forced-finalization path yields a `final_answer` with `error is None` but `budget_exhausted=True`, the live status shows no message at all (the outer code does stream the text, but the status label never reflects the budget-exhausted state beyond the generic "Stopped"/"Done" binary).
3. A secondary `run_agent_turn` failure path can leak an unfriendly `[loop error: ...]` string to the user with no explanatory banner — while this is technically an AgentStep concern, `home.py` does not check `final_step.error` before streaming, so the string ends up as the assistant's durable chat message.

Additionally, there is no protection against exceptions raised *out of* the `run_agent_turn` generator itself (i.e., not yielded as an error step — e.g., if `_client()` raises before the first yield). Such a traceback would crash the Streamlit rerun with a raw exception surface, violating UX-07.

## Warnings

### WR-01: Inline chart under final answer is lost on rerun

**File:** `app/pages/home.py:228-236` (live render) vs. `app/pages/home.py:168-176` (historical render)

**Issue:** On the live turn, the post-stream block renders the last chart inline *above* the "Show reasoning" expander (line 230-232). But on `st.rerun()` (line 244), the historical render loop only replays `turn["content"]` and the static steps inside the expander. `_render_steps_static` renders each tool_result chart *inside* the expander (line 85-86), so after rerun the user no longer sees the inline chart under the answer — it is only reachable by expanding "Show reasoning". This is a visible UX regression between the live turn and every subsequent rerun, and it contradicts UX-05 ("inline under streamed text") from the UI spec.

**Fix:** Persist the inline chart reference alongside the chat turn (or derive it from the stored trace on rerun) and render it in the historical loop:
```python
# In historical render loop (around line 170):
if turn["role"] == "assistant":
    past_steps = get_agent_trace(turn_index)
    if past_steps:
        inline_chart = _last_chart_from_steps(past_steps)
        if inline_chart is not None:
            st.plotly_chart(inline_chart, use_container_width=True)
        with st.expander("Show reasoning", expanded=False):
            _render_steps_static(past_steps)
```
Also consider skipping chart rendering inside `_render_steps_static` to avoid duplicating the figure (or accept the dup — but pick one and document).

### WR-02: Uncaught exceptions from `run_agent_turn` leak traceback to the UI

**File:** `app/pages/home.py:205-215`

**Issue:** The generator loop wraps the `for step in run_agent_turn(...)` call in a `with status:` context, but there is no `try/except` guarding the generator itself. `run_agent_turn` calls `ctx.llm_adapter._client()` (loop.py:146) before its first yield; if the OpenAI client construction raises (bad API key format, network failure during client init, import errors under lazy paths), the exception propagates up through the `with status:` block and Streamlit renders a raw traceback — violating UX-07 ("no traceback leak"). The review prompt explicitly asks for this case.

**Fix:** Wrap the generator consumption in `try/except` and surface a plain-text error inside the status, then close the status as failed:
```python
with status:
    try:
        for step in run_agent_turn(user_msg, ctx):
            collected_steps.append(step)
            _render_step_live(step, status)
            if step.step_type == "final_answer":
                final_step = step
                break
    except Exception as exc:  # noqa: BLE001
        status.write(f"⚠ 에이전트 실행 중 오류: {exc}")
        status.update(label="Error", state="error", expanded=False)
        # No final_step; skip the write_stream/append_chat block below
    else:
        status.update(
            label="Done" if final_step and not final_step.error else "Stopped",
            state="complete",
            expanded=False,
        )
```

### WR-03: Loop-error `final_answer` is streamed verbatim and persisted to chat history

**File:** `app/pages/home.py:217-239`

**Issue:** Per `AgentStep` docstring (loop.py:30-35), a `final_answer` with `error is not None` + `budget_exhausted=True` carries `content=f"[loop error: {error}]"`. Current home.py behavior:
- Line 212: label becomes `"Stopped"` (fine).
- Line 220: prefix is NOT added because `final_step.error` is truthy.
- Line 227: `st.write_stream(_stream_text(final_text))` streams the raw `[loop error: ...]` string.
- Line 239: `append_chat("assistant", final_text)` **persists this string as the assistant's durable chat message**.

After `st.rerun()`, the transcript permanently displays `[loop error: <openai exception>]` as the assistant's turn — which is both an unpleasant UX and potentially leaks infrastructure details (rate-limit messages, internal URLs from openai SDK).

**Fix:** Branch on `final_step.error` and show a localized friendly message while optionally storing the raw text in the trace only:
```python
if final_step is not None:
    if final_step.error:
        friendly = "죄송합니다. 에이전트가 응답을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요."
        st.write_stream(_stream_text(friendly))
        append_chat("assistant", friendly)
        # Still persist trace for debugging via "Show reasoning"
        assistant_index = len(get_chat_history()) - 1
        append_agent_trace(assistant_index, collected_steps)
    else:
        final_text = final_step.content or ""
        if final_step.budget_exhausted:
            prefix = f"*Stopped after {s.app.agent.max_steps} steps; here's what I found.*\n\n"
            final_text = prefix + final_text
        st.write_stream(_stream_text(final_text))
        # ... existing chart + expander + append_chat path
```

## Info

### IN-01: `_render_step_live` silently drops the non-error `final_answer` branch

**File:** `app/pages/home.py:61-63`

**Issue:** The `elif step.step_type == "final_answer":` branch only writes anything when `step.error` is truthy. When a normal final_answer arrives, the function is a no-op — which is intentional (outer code handles streaming) but it means the status container never shows any indicator for the successful terminal event. Not a bug, but a reader scanning the helper would expect symmetric handling across all `AgentStep.step_type` values declared in the Literal (including the unhandled `"budget_exhausted"`, see IN-02).

**Fix:** Add an explicit comment clarifying intent:
```python
elif step.step_type == "final_answer":
    if step.error:
        status.write(f"⚠ {step.error}")
    # Non-error final_answer은 상위에서 write_stream으로 처리 — status에는 노출 안 함.
```

### IN-02: `AgentStep.step_type` Literal includes `"budget_exhausted"` but neither renderer handles it

**File:** `app/pages/home.py:39-63, 72-86` (renderers) and `app/core/agent/loop.py:38` (Literal)

**Issue:** The `AgentStep.step_type` Literal declares four values: `"tool_call"`, `"tool_result"`, `"final_answer"`, `"budget_exhausted"`. However, `run_agent_turn` never yields a step with `step_type="budget_exhausted"` — budget exhaustion is signaled via `final_answer` + `budget_exhausted=True` flag (loop.py:185-191). The renderers in home.py correctly only handle three of the four. If someone later emits `step_type="budget_exhausted"`, both `_render_step_live` and `_render_steps_static` will silently drop it.

**Fix:** Either (a) remove `"budget_exhausted"` from the Literal in loop.py since the flag-on-final_answer pattern is the canonical signal, or (b) add explicit handling in both renderers. Option (a) is cleaner and preserves the current invariant.

### IN-03: `_stream_text` `time.sleep(0.02)` blocks the Streamlit script thread

**File:** `app/pages/home.py:90-94`

**Issue:** `_stream_text` uses `time.sleep(0.02)` per word. For a typical 100-word answer this adds ~2s of wall-clock time on top of render. Streamlit's `write_stream` already handles chunk pacing naturally — the explicit sleep is a cosmetic choice. Not a correctness issue, but worth calling out: if the final text is long (budget-exhausted summaries can be verbose), the user waits visibly longer than needed.

**Fix:** Consider reducing to `0.01` or omitting entirely:
```python
def _stream_text(text: str) -> Iterator[str]:
    for word in text.split(" "):
        yield word + " "
        # No sleep — let Streamlit pace the stream naturally.
```

### IN-04: `test_append_copies_caller_list` is a false-positive test

**File:** `tests/core/test_session_agent_trace.py:43-48`

**Issue:** The test claims "내부 복사본은 영향 없음" (internal copy is unaffected by external mutation). This is true at the **list level** because `append_agent_trace` does `list(steps)` (session.py:66), which creates a shallow copy. However, the test only mutates by appending a *new* dict to the original list — it never tests mutation of an *element* (e.g., `original[0]["step"] = 99`), which *would* leak because the copy is shallow. If the team later relies on this test to protect against element mutation, they'll be caught off-guard.

**Fix:** Either (a) add an element-mutation test that documents the shallow-copy contract, or (b) rename the test to `test_append_is_shallow_copy` to clarify the actual guarantee:
```python
def test_append_is_shallow_copy(self) -> None:
    inner = {"step": 1}
    original = [inner]
    append_agent_trace(0, original)
    inner["step"] = 99  # mutate element (not list)
    stored = get_agent_trace(0)
    # Shallow copy: element mutation DOES leak. Document this.
    self.assertEqual(stored, [{"step": 99}])
```

---

_Reviewed: 2026-04-22T22:10:57Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
