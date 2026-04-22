# Feature Research

**Domain:** Agentic NL-to-data Q&A loop — UFS benchmarking internal tool
**Researched:** 2026-04-22
**Confidence:** MEDIUM-HIGH (ecosystem patterns verified across multiple sources; UFS-specific visualization patterns inferred from domain knowledge + codebase context)

---

## Feature Landscape

### Table Stakes (Users Expect These)

These are the minimum features that prevent users from abandoning the agent and falling back to writing SQL directly in Explorer. Missing any one of these will make the agent feel broken rather than merely incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Streamed answer text** | Any modern chat UI streams; a blank screen that resolves after 30 s feels like a hang | LOW | `openai_adapter.stream_text` already exists; agentic loop must pipe chunks to `st.write_stream` or write incrementally to a placeholder |
| **Live step trace while running** | Users need to know the agent is working and what it is doing — "generating SQL…", "executing…", "got N rows…"; opaque wait feels like a hung process | MEDIUM | Render each tool-call event (name + summary) as it fires; use `st.status` or expanding container that streams steps in real time |
| **Collapsible full trace after answer** | Engineers and power users want to verify reasoning; hiding trace permanently creates a black box; always showing it clutters the answer | LOW | After final answer renders, collapse all step details into `st.expander("Show reasoning trace")`; each item shows tool name, SQL or args, and row count |
| **SQL visible in trace** | Users must be able to see exactly what SQL ran against their data — this is the primary trust anchor; without it the agent is a black box | LOW | Each `run_sql` tool-call entry in the trace must display the sanitized SQL string in a code block |
| **Row count in trace** | Users need to verify the agent found something; "got 0 rows" vs "got 47 rows" is load-bearing information for debugging wrong answers | LOW | Each `run_sql` result in trace shows `→ N rows returned` (or "→ 0 rows — agent will refine") |
| **Error recovery with visible reason** | The agent will hit bad SQL, empty results, or `row_cap` exceeded — silent failure or cryptic stack traces are dealbreakers | MEDIUM | When a tool call fails or returns 0 rows, display a human-readable reason in the trace ("SQL returned 0 rows — retrying with broader filter") and allow the loop to continue up to `max_steps` |
| **Budget-exceeded graceful stop** | If `max_steps=5` is exhausted, the agent must stop with an honest message, not loop forever or show a raw exception | LOW | Detect step-count exhaustion; emit "I could not find a complete answer within the step limit. Here is what I found so far: …" |
| **Plotly chart rendered inline** | This replaces the existing `auto_chart()` heuristic — users arrive expecting a visualization; a table-only answer for "compare across devices" feels like regression | MEDIUM | `make_chart` tool returns chart spec; `home.py` renders via `st.plotly_chart(fig, use_container_width=True)` |
| **Timeout handling** | 30 s `timeout_s` must surface as a user-facing message, not a Python traceback | LOW | Wrap the loop in a timeout; on `TimeoutError` emit "The query took too long. Try narrowing the question." |
| **Answer + data table together** | Final answer prose alone is not enough; users expect to see the underlying data the answer is based on | LOW | After the LLM's final narrative, render the result DataFrame as `st.dataframe()` |
| **Question input with submit** | A text input + submit button (or Enter key) — the fundamental chat entry point | LOW | Already partially exists in `home.py`; replace the old confirm-execute flow with a single submit that launches the agentic loop |

---

### Differentiators (Competitive Advantage for This Internal Tool)

Features that elevate this from "basic NL-to-SQL" to a UFS-specialist analyst. The existing Explorer page already handles manual SQL; the agent earns its keep through these.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **LLM-selected chart type** | The agent chooses `bar` / `heatmap` / `line` / `scatter` based on the semantics of the question and result shape — not a heuristic on column types. "Compare wb_enable across devices" → bar; "all parameters for all devices" → heatmap. This is what `make_chart` enables that `auto_chart` cannot | MEDIUM | `make_chart` tool takes `chart_type`, `x`, `y`, `color`, `title`, `data_ref`; LLM reasons about which type fits the answer. Requires the tool definition to enumerate valid types and require explicit choice |
| **Device × parameter heatmap** | A `chart_type=heatmap` with `x=PLATFORM_ID`, `y=Item`, `z=normalized_value` gives an instant matrix view of all device performance parameters — the canonical UFS cross-device analysis view that users cannot easily get from manual SQL | HIGH | Requires `pivot_to_wide` + `normalize_result` to have run first; Plotly `px.imshow` or `go.Heatmap`; LLM must know to invoke both pre-processing tools before `make_chart` |
| **Brand-vs-brand bar chart** | A filtered bar chart grouping devices by brand prefix (Samsung, OPPO, etc.) against a single parameter value — the most common executive-level UFS question | MEDIUM | Agent uses `run_sql` with a brand filter, then `make_chart(chart_type=bar, x=PLATFORM_ID, y=Result, color=brand)`. Requires `normalize_result` to clean hex/error values before charting |
| **Top-N ranking bar** | "Which devices have the largest X?" → sorted bar chart. Requires the agent to recognize ranking intent and emit `ORDER BY … DESC LIMIT N` SQL autonomously | LOW | Agent generates correct ORDER BY SQL; `make_chart(chart_type=bar, x=PLATFORM_ID, y=Result)` with sorted data. Straightforward once `normalize_result` cleans the Result column |
| **`pivot_to_wide` inside chat** | Long→wide pivot renders in the answer as a properly shaped table (devices as columns, parameters as rows) — exactly the shape domain experts expect from UFS data; raw long-format is unreadable for multi-parameter comparisons | MEDIUM | `pivot_to_wide(category, item)` tool returns a wide DataFrame; rendered via `st.dataframe()`. LLM must know when to invoke it (multi-parameter, multi-device questions) |
| **`normalize_result` before analysis** | UFS `Result` column contains hex strings, `"None"`, error text, and compound `local=…,peer=…` values; automatic normalization before charting or answering means the agent never returns garbage averages or non-numeric chart axes | MEDIUM | `normalize_result` tool applies `clean_result` helper; must be invoked by agent before any numeric analysis. Dependency on `run_sql` preceding it |
| **On-demand schema doc retrieval** | Agent pulls only the UFS spec section relevant to the current question (`get_schema_docs(section)`), keeping per-turn token cost low while retaining full spec depth. Users never have to paste schema context — it's automatic | MEDIUM | Already planned as a tool (`get_schema_docs`); value is that a generic agent would need the user to provide context; this one self-retrieves. Requires spec sections stored accessibly |
| **Disambiguation clarification turn** | When a question is underspecified ("show me the results for device X" — which category?), the agent asks one targeted clarifying question rather than guessing or failing silently. This mirrors how a real analyst would respond | MEDIUM | Agent emits a clarification question as its final output instead of SQL; user replies; next turn includes the clarified question. Requires the loop to detect underspecification (via `get_schema` returning multiple matching categories) and formulate a single focused question. NOTE: only valuable if stateless turns are acceptable; in v1 stateless model, each clarification is a new independent turn |
| **"Why this SQL" rationale in trace** | Each `run_sql` trace entry includes a one-line LLM rationale ("Filtering to InfoCatergory='PERFORMANCE' because the question asks about throughput metrics") — this builds trust and helps users learn the data model | LOW | The LLM already has this reasoning when it constructs the tool call; require the `run_sql` tool definition to include an optional `rationale` argument that the model populates and the UI displays |
| **Confidence signal on answer** | After the final answer, a LOW/MEDIUM/HIGH indicator (based on whether the agent needed all 5 steps, hit errors, or settled on first attempt) signals how much to trust the result | MEDIUM | Computed from loop metadata: 1 step + no errors = HIGH; retries or 0-row recoveries = MEDIUM; budget exceeded or partial answer = LOW. Rendered as a subtle badge next to the answer |

---

### Anti-Features (Things to Explicitly NOT Build in v1)

Anti-features are features that seem reasonable but conflict with the v1 scope defined in PROJECT.md, would introduce unacceptable complexity, or would undermine the core design decisions already made.

| Anti-Feature | Why It Seems Appealing | Why NOT to Build It | Scope Reference |
|--------------|------------------------|---------------------|-----------------|
| **Cross-turn result references ("filter the previous result", "now show that as a heatmap")** | Feels like a natural conversation; users expect chat-like follow-up | v1 is explicitly stateless per turn to keep the loop simple and cheap. Cross-turn DataFrame cache requires a `result_N` ID scheme, session-scoped storage, and cache invalidation. The existing `session_state` chat history is display-only, not executable. Revisit after v1 usage reveals whether follow-ups are common | PROJECT.md Out of Scope: "Cross-turn memory / result references" |
| **Ollama / Anthropic / any non-OpenAI provider for the agentic loop** | Parity with Settings page's multi-provider support feels consistent | Tool-calling API divergence across providers makes testing surface explode. Ollama's tool-calling is community-maintained and diverges frequently. Anthropic's tool-calling schema differs from OpenAI's. v1 validates UX first; provider abstraction is a v2 concern | PROJECT.md Out of Scope: "Ollama, Anthropic, or any non-OpenAI provider in the agentic loop" |
| **General-purpose schema agent (any MySQL table, not just `ufs_data`)** | Would make the agent reusable across other databases the Settings page supports | The entire value proposition is UFS-aware reasoning — `pivot_to_wide`, `normalize_result`, `get_schema_docs` all encode UFS-specific knowledge. A general agent would lose these and require users to re-explain schema quirks every turn | PROJECT.md Out of Scope: "General-purpose agentic Q&A over arbitrary MySQL schemas" |
| **LangGraph / LangChain / OpenAI Agents SDK framework** | Faster agent scaffolding; built-in retry, streaming, tool routing | ~200 lines of raw `chat.completions` + `tools=[]` loop covers this milestone with full control over streaming and budget enforcement. Framework adds a dependency with version churn risk and opaque streaming behavior in Streamlit | PROJECT.md Out of Scope: "Frameworks (LangGraph, OpenAI Agents SDK, LangChain)" |
| **Saved reports / scheduled queries / dashboards** | Power users may want to save an answer for later | Not requested for this milestone; adds persistent storage surface and auth-scoped storage that is out of PRD scope | PROJECT.md Out of Scope: "Saved reports, scheduled queries, dashboards" |
| **Chart libraries beyond Plotly (Altair, Vega, Bokeh)** | Richer chart options | Altair is already in `requirements.txt` but unused; introducing it doubles the charting surface to maintain. Plotly covers `bar / line / scatter / heatmap` needed for all three ship-bar scenarios | PROJECT.md Out of Scope: "Chart libraries beyond Plotly" |
| **New chart types beyond bar / line / scatter / heatmap** | Users may ask for pie charts, box plots, violin plots | Minimum viable surface for v1; the `make_chart` tool schema uses an enum — extending it later requires only a tool-definition change and a renderer. No reason to build now | PROJECT.md Out of Scope: "New chart types beyond bar / line / scatter / heatmap" |
| **RBAC / SSO / multi-concurrent DB sessions** | Enterprise readiness | Out of PRD §1.3 scope; existing `streamlit-authenticator` is sufficient for internal single-team use | PROJECT.md Out of Scope: "RBAC, SSO, multi-concurrent DB sessions" |
| **Per-turn result caching across identical questions** | Reduce API cost for repeated questions | Stateless per turn means there is no session cache to key against anyway. The `row_cap=200` + `max_steps=5` budget bounds cost sufficiently for v1 internal usage | Implicit from stateless-per-turn design decision |
| **Streaming SQL execution (row-by-row)** | Feels more responsive for large result sets | `row_cap=200` + `auto-LIMIT` means result sets are small enough that streaming rows adds complexity with no perceptible benefit. The trace streams; the result arrives as a unit | Implicit from `row_cap=200` design decision |
| **User-editable SQL confirmation step** | The old home.py had a text area for the user to edit generated SQL before execution | This is the flow being replaced. The agentic loop closes the loop autonomously. If users want to write SQL, Explorer exists | Active requirement: "Remove the existing generate SQL → confirm → execute flow" |

---

## Feature Dependencies

```
[Streamed answer text]
    └──requires──> [Live step trace while running]
                       └──requires──> [Tool-call events emitted per step]

[Plotly chart rendered inline]
    └──requires──> [make_chart tool]
                       └──requires──> [pivot_to_wide tool] (for heatmap)
                       └──requires──> [normalize_result tool] (before numeric charting)

[Device × parameter heatmap]
    └──requires──> [pivot_to_wide tool]
    └──requires──> [normalize_result tool]
    └──requires──> [make_chart tool with chart_type=heatmap]

[Brand-vs-brand bar chart]
    └──requires──> [normalize_result tool]
    └──requires──> [make_chart tool with chart_type=bar]

[Top-N ranking bar]
    └──requires──> [normalize_result tool]
    └──requires──> [make_chart tool with chart_type=bar]

["Why this SQL" rationale in trace]
    └──requires──> [Collapsible full trace after answer]
    └──requires──> [SQL visible in trace]

[Confidence signal on answer]
    └──requires──> [Budget-exceeded graceful stop]
    └──requires──> [Error recovery with visible reason]
    └──enhances──> [Collapsible full trace after answer]

[Disambiguation clarification turn]
    └──requires──> [get_schema tool] (to identify ambiguous column values)
    └──conflicts──> [Cross-turn result references] (stateless means clarification is a new turn, not a continuation)

[On-demand schema doc retrieval]
    └──requires──> [get_schema_docs tool]
    └──enhances──> [Disambiguation clarification turn]
```

### Dependency Notes

- **`normalize_result` before any charting:** The UFS `Result` column is untrusted text. Any chart tool call that maps `Result` to a numeric axis will produce garbage or crash without normalization first. The LLM must be instructed (via system prompt or tool description) to always call `normalize_result` before `make_chart`.
- **`pivot_to_wide` before heatmap:** A heatmap of device × parameter requires a wide matrix; the raw long-format data from `run_sql` cannot be fed directly to Plotly's heatmap. The dependency is strict.
- **`cancel` button requires streaming:** A cancel/stop button only makes sense if the loop is streaming steps visibly. In Streamlit's threading model, a cancel button that re-runs the page is the practical mechanism — this requires the loop to check a session-state cancellation flag between steps. Complexity is MEDIUM; deferred to v1.x (see MVP section).
- **"Why this SQL" rationale requires structured tool output:** The `run_sql` tool must include a `rationale` field in its OpenAI tool definition so the model is prompted to populate it. It cannot be extracted from prose after the fact.

---

## MVP Definition

### Launch With (v1 — required to pass ship bar)

These features are directly required by the three ship-bar scenarios in PROJECT.md (cross-device compare, top-N ranking, brand-vs-brand).

- [ ] **Streamed answer text** — without streaming the UX regression from the old Home is perceptible
- [ ] **Live step trace while running** — users must see agent activity, not a blank spinner
- [ ] **Collapsible full trace after answer** — trust anchor for power users and debugging
- [ ] **SQL visible in trace** — minimum transparency; row count alongside it
- [ ] **Error recovery with visible reason** — agent will hit 0-row results on first attempt in real usage
- [ ] **Budget-exceeded graceful stop** — prevents infinite spin on hard questions
- [ ] **Timeout handling** — `timeout_s=30` must surface as a message, not a traceback
- [ ] **Plotly chart rendered inline** — all three ship-bar scenarios require a chart
- [ ] **Answer + data table together** — users need to see the underlying data
- [ ] **LLM-selected chart type** (`make_chart` tool) — bar for ranking, heatmap for device×parameter matrix
- [ ] **`pivot_to_wide` tool** — required for cross-device compare (ship-bar scenario 1)
- [ ] **`normalize_result` tool** — required for brand-vs-brand numeric comparison (ship-bar scenario 3)
- [ ] **Top-N ranking bar** — ship-bar scenario 2 ("Which devices have the largest…?")
- [ ] **Brand-vs-brand bar chart** — ship-bar scenario 3 ("Compare X for Samsung vs OPPO")

### Add After Validation (v1.x)

Add once the three ship-bar scenarios are confirmed working in a real session with actual UFS data.

- [ ] **Cancel/stop button** — requires checking `st.session_state` cancellation flag between agent steps; Streamlit's threading model makes this slightly involved; not blocking for v1
- [ ] **Confidence signal on answer** — computed from loop metadata; adds polish without changing the loop
- [ ] **"Why this SQL" rationale in trace** — add `rationale` field to `run_sql` tool definition; very low implementation cost but easy to defer
- [ ] **Disambiguation clarification turn** — stateless design means this is a new full turn; validate whether users actually hit ambiguous questions before building
- [ ] **Device × parameter heatmap** — the full all-parameters matrix (not just single-parameter comparisons); higher data volume and pivot complexity; useful but not in the three ship-bar scenarios explicitly

### Future Consideration (v2+)

Defer until v1 usage reveals whether these are actually needed.

- [ ] **Cross-turn result references** — only if usage data shows follow-up questions are the dominant pattern; requires a `result_N` ID scheme and session-scoped DataFrame cache
- [ ] **Ollama / Anthropic parity in the agentic loop** — only after v1 UX is validated and provider tool-calling APIs stabilize
- [ ] **General-purpose schema agent** — only if the tool is adopted by teams with non-UFS databases
- [ ] **On-demand schema doc retrieval depth** — current `get_schema_docs` tool is planned; deeper doc indexing (vector search over full spec) is v2 if agents start making schema-reasoning errors

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Streamed answer text | HIGH | LOW | P1 |
| Live step trace while running | HIGH | MEDIUM | P1 |
| SQL visible in trace | HIGH | LOW | P1 |
| Error recovery with visible reason | HIGH | MEDIUM | P1 |
| Plotly chart rendered inline | HIGH | MEDIUM | P1 |
| LLM-selected chart type (`make_chart`) | HIGH | MEDIUM | P1 |
| `pivot_to_wide` tool | HIGH | MEDIUM | P1 |
| `normalize_result` tool | HIGH | MEDIUM | P1 |
| Budget-exceeded graceful stop | HIGH | LOW | P1 |
| Timeout handling | HIGH | LOW | P1 |
| Collapsible full trace after answer | MEDIUM | LOW | P1 |
| Answer + data table together | MEDIUM | LOW | P1 |
| Top-N ranking bar | HIGH | LOW | P1 |
| Brand-vs-brand bar chart | HIGH | LOW | P1 |
| Device × parameter heatmap | HIGH | HIGH | P2 |
| Confidence signal on answer | MEDIUM | MEDIUM | P2 |
| "Why this SQL" rationale in trace | MEDIUM | LOW | P2 |
| Disambiguation clarification turn | MEDIUM | MEDIUM | P2 |
| Cancel/stop button | MEDIUM | MEDIUM | P2 |
| Cross-turn result references | HIGH | HIGH | P3 |
| On-demand schema doc depth (vector) | LOW | HIGH | P3 |

**Priority key:** P1 = Must have for v1 launch / ship bar; P2 = Add after validation; P3 = Future milestone

---

## UFS-Domain-Specific Feature Notes

These patterns are specific to the `ufs_data` long/narrow schema and are not generic NL-to-SQL concerns. They represent the primary reason this agent is UFS-specialized rather than general-purpose.

### Cross-Device Comparison Idioms

**Long→Wide pivot before comparison.** Raw `ufs_data` rows are `(PLATFORM_ID, InfoCatergory, Item, Result)` — one row per parameter per device. Any cross-device comparison of multiple parameters requires `pivot_to_wide(category, item)` to reshape to `devices × parameters` matrix. This is not something MySQL can do dynamically, so it must be a server-side Python tool. The agent must learn to invoke `pivot_to_wide` before any multi-parameter, multi-device analysis.

**Heatmap as the canonical multi-device view.** When a user asks to compare "all performance parameters across all devices," the natural visualization is a `device × parameter` heatmap where cell color encodes normalized value. This requires: `run_sql` → `pivot_to_wide` → `normalize_result` → `make_chart(chart_type=heatmap)`. The agent must be prompted to recognize this pattern.

**Bar chart for single-parameter device ranking.** "Which device has the highest X?" is a ranking question. The correct visualization is a bar chart sorted descending by the normalized numeric value. Requires: `run_sql(ORDER BY ... DESC)` → `normalize_result` → `make_chart(chart_type=bar)`.

**Brand prefix grouping.** `PLATFORM_ID` values encode brand (e.g., `Samsung_UFS_4.0`, `OPPO_UFS_3.1`). Brand-vs-brand analysis requires the agent to recognize brand-prefix patterns in `PLATFORM_ID` and either filter with `WHERE PLATFORM_ID LIKE 'Samsung%'` or group by a derived brand column. This is UFS-specific schema knowledge that must be in the system prompt or `get_schema_docs`.

### Result-Value Normalization Patterns

The `Result` column is the most fragile part of the UFS data model. The agent must invoke `normalize_result` before any numeric analysis. Known patterns that break naive aggregation:

- **Hex strings** (`0x1A3F`) — must convert to decimal
- **`"None"` or `"N/A"` strings** — must become SQL NULL / Python `None`
- **Error strings** (e.g., `"Error: command failed"`) — must become NULL
- **Compound values** (`"local=1024, peer=2048"`) — must be split into separate fields; LLM must decide which sub-value is relevant to the question

The `normalize_result` tool encapsulates `clean_result` from the existing codebase. The agent must be instructed to call it before any chart or numeric comparison; calling it after will produce incorrect results for partially-parsed data.

### Pivot-to-Wide Rendering Inside Chat

After `pivot_to_wide`, the resulting DataFrame is wide and potentially has many columns (one per `PLATFORM_ID`). Rendering this inside a Streamlit chat message via `st.dataframe()` may require `use_container_width=True` and horizontal scrolling. The UX should not truncate columns silently — domain users need to see all device columns to do their analysis. This is a presentation detail but one that distinguishes a useful tool from a frustrating one.

---

## Sources

- [The Six Failures of Text-to-SQL (And How to Fix Them with Agents) — Google Cloud / Medium](https://medium.com/google-cloud/the-six-failures-of-text-to-sql-and-how-to-fix-them-with-agents-ef5fd2b74b68)
- [Designing For Agentic AI: Practical UX Patterns For Control, Consent, And Accountability — Smashing Magazine](https://www.smashingmagazine.com/2026/02/designing-agentic-ai-practical-ux-patterns/)
- [Agentic Analytics: The Complete Guide to AI-Driven Data Intelligence — GoodData](https://www.gooddata.com/blog/agentic-analytics-complete-guide-to-ai-driven-data-intelligence/)
- [Building an Agentic Analytics System — Data Science Collective / Medium](https://medium.com/data-science-collective/building-an-agentic-analytics-system-bc7e8fcd058d)
- [Agent UX in 2025: The New Table Stakes — Nexumo / Medium](https://medium.com/@Nexumo_/agent-ux-in-2025-the-new-table-stakes-dd189c7c2718)
- [Your ReAct Agent Is Wasting 90% of Its Retries — Towards Data Science](https://towardsdatascience.com/your-react-agent-is-wasting-90-of-its-retries-heres-how-to-stop-it/)
- [Detecting Ambiguities to Guide Query Rewrite for Robust Conversations in Enterprise AI Assistants — arXiv](https://arxiv.org/html/2502.00537v1)
- [Agentic Plan Caching: Test-Time Memory for Fast and Cost-Efficient LLM Agents — arXiv](https://arxiv.org/abs/2506.14852)
- PROJECT.md Out-of-Scope constraints (primary source for anti-features)
- .planning/codebase/ARCHITECTURE.md — existing home.py flow analysis

---

*Feature research for: Agentic NL-to-data Q&A loop — UFS benchmarking internal tool (replacing Home single-shot NL→SQL)*
*Researched: 2026-04-22*
