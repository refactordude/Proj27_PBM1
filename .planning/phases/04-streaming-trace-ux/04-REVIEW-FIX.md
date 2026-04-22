---
phase: 04-streaming-trace-ux
fixed_at: 2026-04-23T00:00:00Z
review_path: .planning/phases/04-streaming-trace-ux/04-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 04: Code Review Fix Report

**Fixed at:** 2026-04-23T00:00:00Z
**Source review:** .planning/phases/04-streaming-trace-ux/04-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (WR-01, WR-02, WR-03 — Info findings out of scope per `fix_scope: critical_warning`)
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: Inline chart under final answer is lost on rerun

**Files modified:** `app/pages/home.py`
**Commit:** ec76dcc
**Applied fix:** In the historical render loop (assistant turn branch), extracted the latest chart from the stored AgentStep trace via `_last_chart_from_steps(past_steps)` and rendered it with `st.plotly_chart(..., use_container_width=True)` ABOVE the "Show reasoning" expander. The existing `_render_steps_static` still renders charts inside the expander (per the review guidance: "render it inside the expander AND render it ABOVE the expander"), so on rerun the user now sees the chart both inline under the assistant answer and inside the collapsed reasoning. Satisfies UX-05 across reruns.

### WR-02: Uncaught exceptions from `run_agent_turn` leak traceback to the UI

**Files modified:** `app/pages/home.py`
**Commit:** 968cea2
**Applied fix:** Wrapped the `for step in run_agent_turn(...)` loop (inside `with status:`) in `try/except Exception`. On exception: set a `generator_failed` flag, close the status container cleanly via `status.update(label="Error", state="error", expanded=False)`, and outside the `with status:` block render a non-leaky `st.error("Agent encountered an unexpected error. Check logs.")` — no traceback, no raw exception message. The successful path uses the `else:` branch to update status with the original `"Done"`/`"Stopped"` label logic. Downstream `if final_step is not None:` block is skipped naturally because `final_step` remains `None` on failure. UX-07 compliance.

### WR-03: Loop-error `final_answer` is streamed verbatim and persisted to chat history

**Files modified:** `app/pages/home.py`
**Commit:** 8a2d08e
**Applied fix:** Added an `if final_step.error:` branch ahead of the normal terminal-answer path. In the error branch: stream a clean user-facing message (`"(An error occurred while processing your question — please try rephrasing.)"`) via `st.write_stream(_stream_text(friendly))`, persist ONLY the friendly text to chat_history via `append_chat("assistant", friendly)`, and still attach the original `collected_steps` trace via `append_agent_trace(...)` for "Show reasoning" debugging. The raw `[loop error: ...]` string is never streamed or stored in chat_history, preventing OpenAI SDK internals (rate-limit messages, internal URLs) from leaking into the durable transcript. The non-error branch retains the existing budget-exhausted prefix logic, chart render, trace expander, and persistence behavior.

## Verification

**3-tier verification performed for each fix:**

- Tier 1 (minimum): Re-read modified sections of `app/pages/home.py` after each edit; confirmed fix text present and surrounding code intact.
- Tier 2 (preferred): `python -c "import ast; ast.parse(open('app/pages/home.py').read())"` — EXIT=0 after each fix.
- Additional gate: `python -m unittest discover tests` — 121 tests passing before and after each of the three fixes.

**Final smoke (post all fixes):**

- `python -c "import ast; ast.parse(...)"` on `app/pages/home.py` → exit 0.
- `grep -c 'try:' app/pages/home.py` → 1 (WR-02 try/except present).
- Full test suite: 121 tests, OK.

## Notes

- Info findings (IN-01 through IN-04) are out of scope for this iteration (`fix_scope: critical_warning`) and were not addressed.
- REVIEW-FIX.md is not committed by the fixer — the orchestrator/workflow handles that commit.

---

_Fixed: 2026-04-23T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
