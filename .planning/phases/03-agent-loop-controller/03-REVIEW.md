---
phase: 03-agent-loop-controller
reviewed: 2026-04-22T21:32:27Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - app/core/agent/loop.py
  - app/core/agent/__init__.py
  - app/core/logger.py
  - tests/core/agent/test_loop.py
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-04-22T21:32:27Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

The ReAct loop implementation is structurally sound and aligns with the phase
contract (AGENT-01..09, OBS-02). All the headline safety invariants hold under
static review:

- `parallel_tool_calls=False` is present on **both** `create()` call sites
  (main loop line 183, forced finalization line 101).
- `tool_choice="none"` appears only in `_forced_finalization` (line 100);
  the main loop uses `tool_choice="auto"` (line 182).
- `max_steps` is enforced against a counter that increments **per tool call**
  (line 260), not per response — correct semantics for AGENT-03.
- Budget checks run before every `create()` call (line 149-155), so an
  exhausted budget always leads to exactly one forced finalization call with
  no silent exit.
- `tool_call_id` is round-tripped correctly: the `id` from the assistant
  `tool_calls` entry (line 246) is reused as the `tool_call_id` on the tool
  response (line 326).
- `ValidationError` on tool args (line 299) and generic tool exceptions
  (line 313) are caught and fed back as tool messages — they never escape
  the loop.
- `log_llm()` is called exactly once per `create()` round-trip, both for the
  main path (line 197) and the forced finalization (line 109).
- Zero `streamlit` imports; the static check in `StreamlitAgnosticTest`
  backstops this, and the lazy `__getattr__` in `app/core/agent/__init__.py`
  correctly defers `loop` import to break the `app.core.config` cycle.
- `AgentStep` ordering is correct: `tool_call` yielded before dispatch
  (line 277), `tool_result` after (line 331), `final_answer` last.
- Tests use `MagicMock` on the OpenAI client but keep the real `RunSqlArgs`
  for validation, and assertions are on call_count / kwargs / step_types —
  no SQL strings are asserted (TEST-05 discipline satisfied).

The findings below are focused on correctness at the edges (cumulative token
accounting across turns, docstring/implementation drift on the tokenizer
heuristic) and a small number of minor observability/style items. None rise
to Critical — the loop is safe to wire into Phase 4.

## Warnings

### WR-01: `cumulative_tokens` double-counts prompt history across `create()` calls

**File:** `app/core/agent/loop.py:217-222`
**Issue:** Each `resp.usage.prompt_tokens` value already includes the full
running conversation that was sent to the model on that round-trip. Because
every subsequent `create()` call resends an ever-growing `messages` list,
`prompt_tokens` grows roughly linearly. Accumulating it with `+=` therefore
sums an O(n²) series rather than the true token cost of the turn. On a
6-step loop with ~3k prompt tokens, the loop will cross a 30k cap several
steps before the real usage does, triggering premature forced finalization.
This is over-conservative (safety-positive) but it makes `max_context_tokens`
behave very differently from its name — users setting `30_000` will see the
budget trip at roughly 10-15k of actual prompt size.
**Fix:** Track the *latest* prompt_tokens plus the sum of completion_tokens
and tool-result token estimates, rather than accumulating prompt_tokens:
```python
usage = getattr(resp, "usage", None)
if usage is not None:
    # prompt_tokens already includes all prior turns' history.
    latest_prompt_tokens = int(getattr(usage, "prompt_tokens", 0))
    completion_delta = int(getattr(usage, "completion_tokens", 0))
    cumulative_tokens = latest_prompt_tokens + completion_delta + tool_result_tokens_so_far
```
or track `completion_tokens` and tool-result estimates additively and read
prompt_tokens only from the most recent response. Either approach restores
the invariant that `cumulative_tokens <= actual wire-token cost`.

### WR-02: `loop_step_index` semantics drift between create() calls and tool events

**File:** `app/core/agent/loop.py:146, 261, 344`
**Issue:** The comment on line 146 says `loop_step_index` "increments per
create() round-trip", but inside the tool-call dispatch loop it is also
incremented per tool call (line 261) and again once at line 344 after the
batch. When a response returns one tool call (the normal case under
`parallel_tool_calls=False`), the sequence is: create() logs step_index=0,
tool_call/tool_result yield step_index=1, line 344 bumps to 2, next
create() logs step_index=2 — i.e. step_index=1 in the log file corresponds
to no LLM call, only to tool execution. Consumers of `llm.log` that expect
"consecutive step_index per LLM call" will see gaps (0, 2, 4, ...). The
forced finalization also logs whatever `loop_step_index` happens to be at
budget-check time, which may or may not be consecutive with the last main
call depending on how many tool calls were dispatched in the previous
response.
**Fix:** Either (a) rename the variable and docstring to make clear it is a
monotonic event counter (covers both LLM calls and tool events), or (b)
split into two counters — a `llm_call_index` that increments only before
each `create()` and is passed to `log_llm`, plus a separate `event_index`
used for AgentStep yields. Option (b) better matches the docstring on
line 146 and the OBS-02 requirement ("once per create() round-trip").

### WR-03: First-`create()` failure path skips forced finalization

**File:** `app/core/agent/loop.py:207-215`
**Issue:** If the very first `create()` raises (network error, invalid API
key, rate limit), the loop yields a single `AgentStep` whose `content` is
`f"[loop error: {error}]"` and returns. This path does **not** flow through
`_forced_finalization` and does not set `budget_exhausted=True`, so Phase 4
UI code branching on `budget_exhausted` will treat this as a clean final
answer containing a raw error string. The user sees `"[loop error: ...]"`
in the chat bubble. That's probably the intended behaviour (no point
retrying if the API itself failed), but it is not documented on the AgentStep
dataclass and there is no test covering it — so a future refactor could
quietly break it.
**Fix:** Add an `error` field assertion + docstring note that `final_answer`
with a non-None `error` represents a loop-level failure (as distinct from
`budget_exhausted`). Add a unit test that sets `side_effect=RuntimeError(...)`
on the first `create()` and asserts:
- exactly one `AgentStep` yielded
- `step_type == "final_answer"`
- `error` is populated and equals the raised string
- `budget_exhausted` is False

## Info

### IN-01: Docstring says "char/4" but implementation is "bytes/4"

**File:** `app/core/agent/loop.py:52, 72-76`
**Issue:** Line 52 comment and the `_estimate_tokens` docstring both say
"char/4 heuristic", but the implementation is
`len(text.encode("utf-8")) // 4` — byte count, not character count. For
ASCII the two are identical (which is why the test at line 280 passes: 5000
ASCII `x` = 5000 bytes = 5000 chars). For CJK or emoji-heavy tool results,
byte-count produces ~3x the token estimate per character, making the cap
trip earlier on non-English content. This is safety-positive but the
docstring is misleading.
**Fix:** Either change the comment to "UTF-8 byte / 4 heuristic" (which is
what the code actually does and what `CONTEXT.md` seems to intend for
conservative bounds) or change the implementation to `len(text) // 4`.
Recommend keeping the bytes/4 behaviour and fixing the comments, since
bytes/4 is the safer bound for multi-byte content.

### IN-02: Duplicated `parallel_tool_calls=False` / `timeout=_REQUEST_TIMEOUT` kwargs across two call sites

**File:** `app/core/agent/loop.py:96-103, 178-185`
**Issue:** The invariant "every create() must pass `parallel_tool_calls=False`
and `timeout=_REQUEST_TIMEOUT`" is enforced by hand at two call sites. The
test `test_every_create_call_has_parallel_tool_calls_false` verifies this
dynamically, but a third `create()` added later (e.g. a retry branch)
could silently omit either kwarg. Since both kwargs are AGENT-01/08 gate
invariants, consider a tiny wrapper.
**Fix (optional):**
```python
def _safe_create(client, **kwargs):
    kwargs.setdefault("parallel_tool_calls", False)
    kwargs.setdefault("timeout", _REQUEST_TIMEOUT)
    return client.chat.completions.create(**kwargs)
```
Keeps both call sites honest and is a single-line change at each site. Not
strictly required — the test gate is adequate for now.

### IN-03: Misleading comment in `test_max_context_tokens_triggers_finalization`

**File:** `tests/core/agent/test_loop.py:280-281`
**Issue:** The comment says "5000자 payload → char/4 heuristic으로 1250
tokens" but the implementation uses bytes/4 (see IN-01). For the ASCII `"x"
* 5000` payload they are numerically identical, so the test passes, but the
comment will mislead the next reader who tries to adapt the test for
non-ASCII content.
**Fix:** Change the comment to "5000-byte ASCII payload → bytes/4 heuristic
→ 1250 tokens" to match the actual implementation.

### IN-04: `_SYSTEM_PROMPT` is a module-level constant, not configurable

**File:** `app/core/agent/loop.py:42-49`
**Issue:** The system prompt is hard-coded as a module constant. `AgentConfig`
(`app/core/agent/config.py`) exposes `model`, `max_steps`, `row_cap`,
`timeout_s`, `allowed_tables`, `max_context_tokens`, but not the system
prompt. If the team wants to A/B test prompt variants (or localize) it
requires a code change. This is probably intentional for v1 — prompt
stability is a safety property — but it is worth noting so the decision is
explicit rather than accidental.
**Fix (optional):** Add `system_prompt: str | None = None` to `AgentConfig`
with a clear default fallback to `_SYSTEM_PROMPT` when `None`. Out-of-scope
for this phase; raise as a Phase 4+ consideration.

---

_Reviewed: 2026-04-22T21:32:27Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
