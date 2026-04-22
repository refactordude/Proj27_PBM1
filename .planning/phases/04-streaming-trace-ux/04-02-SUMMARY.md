---
phase: 04-streaming-trace-ux
plan: 02
subsystem: ui
tags: [streamlit, home-page, agent-ux, ui-rewrite, react-loop]

# Dependency graph
requires:
  - phase: 04-streaming-trace-ux
    plan: 01
    provides: _AGENT_TRACE_KEY + append_agent_trace/get_agent_trace in app/core/session.py
  - phase: 03-agent-loop-controller
    provides: run_agent_turn iterator + AgentStep dataclass via lazy re-export in app/core/agent/__init__.py
  - phase: 01-foundation
    provides: AgentConfig under s.app.agent; OpenAIAdapter class-name used for SAFE-06 detection
provides:
  - Agentic Home page — single-file consumer of run_agent_turn with live trace UX
  - Live-trace pattern: st.status outer container + status.write/status.code/status.plotly_chart for streaming steps
  - Trace re-render for past turns via get_agent_trace keyed by assistant-message history index
affects: [05-ship-bar]

# Tech tracking
tech-stack:
  added: [pytest (installed in .venv so regression gate runs venv-local)]
  patterns:
    - "Helper-before-top-level ordering: Streamlit executes module body top-to-bottom, so _render_step_live / _render_steps_static / _stream_text / _last_chart_from_steps / _render_recent_queries are defined before any st.* call that references them."
    - "Budget-exhausted vs error split uses AgentStep.budget_exhausted AND (not step.error) — matches the loop.py contract where error=None + budget_exhausted=True means forced-finalization, error!=None + budget_exhausted=True means network failure."
    - "Assistant-index as trace key: after append_chat('assistant', final_text), assistant_index = len(get_chat_history()) - 1 is used to call append_agent_trace — on rerun the same index keys the expander re-render."
    - "Non-OpenAI guard via class-name string compare (llm_adapter.__class__.__name__ == 'OpenAIAdapter') — avoids importing OpenAIAdapter at module scope and keeps Ollama/other adapters loadable for Settings/Explorer paths."
    - "Trace slot reset on 대화 초기화: direct del st.session_state['agent_trace_v1'] alongside reset_chat() — keeps history/trace in lock-step without adding a new helper in Plan 01's scope."

key-files:
  created: []
  modified:
    - app/pages/home.py

key-decisions:
  - "Kept the three preserved Korean literals (대화 초기화, 최근 질의, 최근 질의 panel header) each to exactly one occurrence per HOME-03 grep contract. The original Write-tool output had them appearing twice (once in comment/docstring, once in st.button/st.subheader); the comment/docstring occurrences were rewritten in English/Romanized form to keep the grep count at exactly 1."
  - "Did NOT call require_login() inside home.py. Auth is centralized in app/main.py before st.navigation dispatches pages, mirroring the existing pattern in explorer.py/compare.py/settings_page.py."
  - "Used s.app.agent directly as AgentConfig (not s.app.agent.agent) per app/core/config.py wiring — AppConfig.agent IS the AgentConfig instance."
  - "Word-level _stream_text generator (0.02s sleep/word) for UX-04 — matches CONTEXT.md Claude's-Discretion preference over char-level for less flicker."
  - "Rendered chart inside expander AND below the streamed text (via _last_chart_from_steps) so the chart remains visible when the expander collapses — per UI-SPEC's chart-placement note."
  - "Early-exit guard uses _render_recent_queries() before st.stop() to keep the 최근 질의 panel visible even when DB/LLM unavailable."

patterns-established:
  - "Live trace renderer split into _render_step_live(step, status) and _render_steps_static(steps) — same switch semantics with different container target."
  - "disabled= on st.chat_input is the v1 answer to non-OpenAI LLM guard; no separate redirect button needed."

requirements-completed:
  - UX-01
  - UX-02
  - UX-03
  - UX-04
  - UX-05
  - UX-06
  - UX-07
  - HOME-01
  - HOME-02
  - HOME-03
  - HOME-04
  - SAFE-06

# Metrics
duration: 20 min
completed: 2026-04-23
---

# Phase 4 Plan 02: Rewrite app/pages/home.py Summary

**One-liner:** Full rewrite of `app/pages/home.py` from the old `pending_sql` preview/Execute flow to a single-shot agentic ReAct consumer driving `run_agent_turn` with live `st.status` trace streaming, word-level `st.write_stream` final answer, collapsible `st.expander("Show reasoning")`, inline `st.plotly_chart` charts, and SAFE-06 OpenAI-only lockout.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rewrite `app/pages/home.py` per UI-SPEC grep contract | `b6ea77f` | `app/pages/home.py` (246 lines, 209 insertions / 127 deletions) |
| 2 | Static smoke verification (AST + import graph + sibling-page diff + pytest) | _verification-only — no source change, no commit_ | — |

## Output File

- **Path:** `app/pages/home.py`
- **Line count:** 246 lines
- **Module structure (top → bottom):**
  1. Module docstring + imports (lines 1–24)
  2. Helper functions — `_render_step_live`, `_render_steps_static`, `_stream_text`, `_last_chart_from_steps`, `_render_recent_queries` (lines 32–117)
  3. Top-level page body — settings, metric cards, LLM resolution, guards, chat-history render loop, `st.chat_input`, submit handler (lines 124–244)
  4. Final `_render_recent_queries()` call (line 246)

## Grep-Contract Results (all assertions passed)

### Required presence

| Token | Required | Observed |
|---|---|---|
| `st.status(` | ≥ 1 | 1 |
| `st.write_stream(` | ≥ 1 | 1 |
| `st.expander("Show reasoning"` | ≥ 1 | 2 (one live in submit handler, one for past-turn re-render) |
| `st.plotly_chart(` | ≥ 1 | 2 (inline below streamed text + inside _render_steps_static) |
| `run_agent_turn(` | ≥ 1 | 2 (import + invocation) |
| `language="sql"` | ≥ 1 | 3 (live trace, static trace, recent-queries panel) |
| `OpenAIAdapter` | ≥ 1 | 2 (SAFE-06 comment + class-name compare) |
| `disabled=` | ≥ 1 | 2 (chat_input keyword + call-site value) |
| `*Stopped after` | ≥ 1 | 1 (UX-06 prefix literal) |
| `append_agent_trace(` | ≥ 1 | 1 |
| `get_agent_trace(` | ≥ 1 | 1 |

### Forbidden presence (all zero — HOME-02 deletion contract)

| Token | Required | Observed |
|---|---|---|
| `pending_sql` | 0 | 0 |
| `extract_sql_from_response` | 0 | 0 |
| `auto_chart` | 0 | 0 |
| `st.text_area(` | 0 | 0 |
| `st.exception(` | 0 | 0 |

### Preserved-literal presence (HOME-03 — each exactly 1)

| Token | Required | Observed |
|---|---|---|
| `대화 초기화` | 1 | 1 |
| `최근 질의` | 1 | 1 |
| `등록된 DB` | 1 | 1 |
| `등록된 LLM` | 1 | 1 |
| `현재 DB` | 1 | 1 |

## Streamlit-Component → REQ-ID Coverage Map

| Streamlit component in home.py | Line(s) | Requirements covered |
|---|---|---|
| `st.status("Thinking...", expanded=True)` inside `with st.chat_message("assistant")` | 203 | **UX-01** (live trace container) |
| `status.code(step.sql, language="sql")` (run_sql branch) + `st.code(step.sql, language="sql")` (static re-render) + recent-queries panel | 42, 76, 117 | **UX-02** (SQL rendering) |
| `with st.expander("Show reasoning", expanded=False)` (past-turn loop + post-final) | 175, 235 | **UX-03** (collapsible trace) |
| `st.write_stream(_stream_text(final_text))` + `_stream_text` word-level generator | 90–94, 227 | **UX-04** (progressive reveal) |
| `status.plotly_chart(step.chart, use_container_width=True)` + `st.plotly_chart(last_chart, use_container_width=True)` + `st.plotly_chart` inside `_render_steps_static` | 60, 86, 232 | **UX-05** (inline charts) |
| `f"*Stopped after {s.app.agent.max_steps} steps; here's what I found.*\n\n"` | 222–225 | **UX-06** (budget-exhausted prefix) |
| `status.write(f"⚠ {step.tool_name}: {step.error}")` + `st.markdown(f"⚠ {step.tool_name}: {step.error}")` (no `st.exception`, no traceback) | 55, 63, 79 | **UX-07** (human-readable error lines) |
| `st.chat_input("질문을 입력하세요...", disabled=not is_openai)` feeding directly into `run_agent_turn(user_msg, ctx)` | 179–182, 205 | **HOME-01** (direct-submit) |
| Absence of `pending_sql`/`extract_sql_from_response`/`auto_chart`/`st.text_area` | (zero occurrences) | **HOME-02** (deletion) |
| Metric cards (`등록된 DB`/`등록된 LLM`/`현재 DB`) + `대화 초기화` button + history-loop render + `최근 질의` panel | 128–132, 160, 168–176, 108 | **HOME-03** (preserved surface) |
| `append_chat("user", user_msg)` + `append_chat("assistant", final_text)` (only final text, no per-step writes) paired with `append_agent_trace(assistant_index, collected_steps)` / `get_agent_trace(turn_index)` | 186, 239, 242, 173 | **HOME-04** (chat_history = user+final only; traces in _AGENT_TRACE_KEY) |
| `is_openai = llm_adapter.__class__.__name__ == "OpenAIAdapter"` + `st.info(...)` banner + `disabled=not is_openai` + guarded `if user_msg and is_openai:` (so `run_agent_turn` is NOT invoked when false) | 152, 154–157, 181, 184 | **SAFE-06** (OpenAI-only lockout) |

## Verification Evidence

### Task 1 — automated verify (all passed)

```
parse OK
pending_sql=0 OK
extract_sql_from_response=0 OK
auto_chart=0 OK
st.status>=1 OK
st.write_stream>=1 OK
expander(Show reasoning)>=1 OK
st.plotly_chart>=1 OK
run_agent_turn>=1 OK
language=sql>=1 OK
OpenAIAdapter>=1 OK
disabled>=1 OK
등록된 DB=1 OK
등록된 LLM=1 OK
현재 DB=1 OK
Stopped after>=1 OK
st.exception=0 OK (UX-07)
```

### Task 2 — static smoke

1. **AST parse:** `python -c "import ast; ast.parse(open('app/pages/home.py').read())"` → `AST OK`
2. **Import graph:** `app.core.agent`, `app.core.agent.context`, `app.core.runtime`, `app.core.session` all resolve via `importlib.util.find_spec` → `import graph OK`
3. **Symbol/contract:** `from app.core.agent import AgentStep, run_agent_turn`; `from app.core.agent.context import AgentContext`; 6 session-helper imports; `inspect.signature(AgentContext)` confirms `db_name` is a required positional/keyword parameter → `symbol/contract OK`
4. **Sibling pages untouched:** `git diff --name-only HEAD~1 HEAD -- app/pages/explorer.py app/pages/compare.py app/pages/settings_page.py` → empty ✓ (HOME-05)
5. **Full regression gate:** `pytest tests/ -x -q` → **121 passed in 9.22s** (identical to pre-plan baseline — zero regressions across Phase 1/2/3 tests including the Plan 01 `test_session_agent_trace.py` suite)

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 3 — Blocking] Installed missing deps in `.venv/` so the regression gate could run**
- **Found during:** Task 2 baseline run (pre-existing — not caused by this plan's code)
- **Issue:** `.venv/` was a minimal install missing `httpx`, `PyYAML`, `pymysql`, `pandas`, `plotly`, `openai`, `pydantic`, `sqlparse`, `openpyxl`, `altair`, `requests`, `streamlit-authenticator`, `python-dotenv`, `bcrypt`, `sqlalchemy`, and `pytest` itself. Without these, `pytest tests/ -x -q` errored on `ModuleNotFoundError: No module named 'httpx'` (and subsequently `yaml`), preventing the SC "Full test suite still passes" check. Also, the system `pytest` at `~/.local/bin/pytest` was being invoked instead of the venv's pytest, compounding the issue.
- **Fix:** Installed all packages pinned in `requirements.txt` into `.venv/` via `pip install -q ...`, then installed `pytest` into the venv so `which pytest` resolves to `.venv/bin/pytest`. Not a code change — only venv alignment with the repo's declared dependency contract (same rationale as Plan 01's streamlit install — see 04-01-SUMMARY.md key-decision #1).
- **Files modified:** None in the repo. `.venv/` is gitignored.
- **Commit:** — (infrastructure alignment, no tracked file changed)

**2. [Rule 1 — Contract fix] Trimmed Korean literals to exactly one occurrence each**
- **Found during:** Task 1 post-write grep (`grep -c '대화 초기화' app/pages/home.py` returned 2, same for `최근 질의`).
- **Issue:** The initial write placed `대화 초기화` in both a code comment and the `st.button` label; `최근 질의` in both the docstring and `st.subheader`. HOME-03 spec requires exactly 1 occurrence.
- **Fix:** Rewrote the code comment to `chat-reset button (label literal required by grep contract)` and the docstring to `Recent-queries 패널 — Explorer/Compare 등이 기록한 쿼리를 노출.` preserving user-facing Korean in `st.button`/`st.subheader` only.
- **Files modified:** `app/pages/home.py`
- **Commit:** Folded into `b6ea77f` (same task).

### Out-of-scope observations (not fixed, not logged as deferred)

None discovered. Sibling pages remained untouched; no unrelated warnings surfaced during the 121-test regression run.

## Authentication gates

None encountered. The plan executed fully offline (no OpenAI API calls, no DB connection) since Task 2 limits itself to static smoke + unit-test regression. End-to-end live smoke is explicitly deferred to Phase 5 ship-bar (SHIP-01..03) per CONTEXT.md "Manual smoke test" note.

## Known stubs

None. Every new code path in `app/pages/home.py` is wired to a real implementation from Phase 3 (`run_agent_turn`, `AgentStep`, `AgentContext`) or Plan 01 (`append_agent_trace`, `get_agent_trace`). The SAFE-06 `st.info` banner is an intentional user-facing redirect, not a stub.

## Self-Check: PASSED

- ✓ `app/pages/home.py` exists at 246 lines (FOUND).
- ✓ Commit `b6ea77f` exists in `git log --oneline --all` (FOUND).
- ✓ All grep-contract assertions from the plan's `<verify>` section pass (re-ran after commit — values unchanged).
- ✓ Sibling pages `explorer.py`, `compare.py`, `settings_page.py` show zero diff vs HEAD~1 (HOME-05 verified).
- ✓ `pytest tests/ -x -q` reports **121 passed in 9.22s** — identical to pre-plan baseline.
- ✓ Task 1 acceptance criteria (9/9) satisfied.
- ✓ Task 2 acceptance criteria (6/6) satisfied.
- ✓ 12 requirements from frontmatter — UX-01..07 + HOME-01..04 + SAFE-06 — each covered by a specific Streamlit component per the coverage map above.
