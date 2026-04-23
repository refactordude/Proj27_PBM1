# Milestones

## v1.0 Agentic UFS Q&A (Shipped: 2026-04-23)

**Phases completed:** 5 phases, 13 plans, 38 tasks

**Key accomplishments:**

- Pydantic AgentConfig model exposing every per-turn agent budget (max_steps=5, row_cap=200, timeout_s=30, max_context_tokens=30_000), the ufs_data allowlist, and the swappable gpt-4.1-mini model selector — all with ge/le bounds and full stdlib-unittest coverage.
- AgentContext dataclass with instance-level `_df_cache` (field(default_factory=dict)) satisfying AGENT-07 stateless-per-turn, plus four-test stdlib-unittest coverage proving `ctx1._df_cache is not ctx2._df_cache` at the shape level.
- `Tool` @runtime_checkable typing.Protocol and `ToolResult` Pydantic BaseModel landing at `app/core/agent/tools/_base.py`, with 7-test stdlib-unittest coverage proving structural isinstance, negative isinstance, ToolResult defaults, full payload, arbitrary chart types, and toy-tool round-trip through a real AgentContext.
- 30-second httpx.Timeout wired onto every OpenAI chat.completions.create call via a DRY module-level constant, bounding all four network phases (connect/read/write/pool) and closing the indefinite-hang vector on both generate_sql and stream_text.
- `AppConfig` now composes `AgentConfig` via `default_factory=AgentConfig`, the YAML round-trip and backward-compat-with-old-YAML are unit-test-proven, `config/settings.example.yaml` documents the new `app.agent` block, and the Phase 4 handoff audit (`01-05-SESSION-AUDIT.md`) confirms Settings UI compliance with OBS-03 and earmarks `pending_sql` / `pending_sql_edit` for HOME-02 removal.
- SELECT-only agent tool wired through two safety gates (sql_safety + sqlparse allowlist walker), SAFE-03 framing envelope with 500-char per-cell cap, and OBS-01 JSONL audit logging on every execution path.
- Orientation tool that returns tables + columns + distinct PLATFORM_ID / InfoCatergory values as compact JSON so the agent can pick filter arguments without hallucinating column names or category strings.
- TOOL-03 pivot_to_wide tool reshapes long-form ufs_data into a wide per-PLATFORM_ID DataFrame via `df.pivot_table(aggfunc='first')`, caches it in `AgentContext._df_cache`, and returns `df_ref` — plus the non-breaking AgentContext.current_tool_call_id ambient-threading slot that unblocks this and downstream cache-key tests.
- TOOL-04 normalize_result applies UFS spec §5 cleanup (hex→int, numeric parse, null-likes→pd.NA, compound 'local=1,peer=2' row-split with parameter suffix) to a cached DataFrame and writes the cleaned result back under a deterministic `f'{data_ref}:normalized'` key, returning df_ref for downstream make_chart consumption.
- On-demand UFS spec §1–§7 retriever with module-level eager-load cache, Pydantic-bounded section arg, and 7 scaffold text files ready for Phase 5 authoring.
- TOOL-06 `make_chart` implemented via plotly.express — Literal-validated chart_type (bar/line/scatter/heatmap), cache-backed DataFrame lookup, and Plotly Figure returned in ToolResult.chart for Phase 4 UI rendering.
- Flat `TOOL_REGISTRY: dict[str, Tool]` wiring all 6 Wave 1 agent tools, plus registry shape/Protocol tests and the SAFE-07 InfoCategory grep guard with a self-meta-test that proves the scanner works.
- ReAct loop over OpenAI tool-calling with triple-gate budget enforcement (max_steps / timeout_s / max_context_tokens) and forced finalization via tool_choice="none" — all in a Streamlit-agnostic pure-Python module.
- Integration-test suite for the ReAct loop using mocked OpenAI clients — 7 tests across 6 TestCase classes covering SC1-SC5 + AGENT-07 regression, with strict TEST-05 discipline (assertions on loop-control, not SQL content).
- One-liner:
- 3 mocked-DB E2E scenarios exercising the full agent dispatch chain (run_sql / pivot_to_wide / normalize_result / make_chart) end-to-end with real Plotly Figure output, plus log sanity + sibling-page AST smoke + README rewritten around the Agentic UFS Q&A flow.

---
