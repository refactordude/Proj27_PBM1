---
phase: 05-test-polish
status: passed
score: "5/5 (all automated + live-DB manual validation confirmed by operator)"
checked: 2026-04-23T00:00:00Z
live_db_validated: 2026-04-23T00:00:00Z
---

# Phase 5 Verification — Test & Polish

## Success Criteria

| SC | Requirement | Check | Result | Status |
|----|-------------|-------|--------|--------|
| SC1 | TEST-01..05 aggregate — full suite green | `python -m unittest discover tests` | 129 tests, OK | ✅ automated |
| SC2 | SHIP-01 (wb_enable) E2E | `ShipBar01WbEnableTest` against mocked DB + real TOOL_REGISTRY | OK | ✅ automated (mocked DB) |
| SC3 | SHIP-02 (capacity) E2E | `ShipBar02CapacityTest` | OK | ✅ automated (mocked DB) |
| SC4 | SHIP-03 (brand compare) E2E | `ShipBar03LifetimeBrandCompareTest` | OK | ✅ automated (mocked DB) |
| SC5 | Log sanity — JSONL well-formed, no tracebacks | `LogSanityTest` on queries.log + llm.log | OK | ✅ automated |

### Live-DB validation (human_needed)

ROADMAP SC2/3/4 specify "seeded `ufs_data` database". The automated tests exercise the full agentic code path (run_sql → pivot_to_wide / normalize_result → make_chart) end-to-end with a mocked DB adapter returning fixture rows shaped like real UFS data. The only piece automated tests cannot cover is actual MySQL I/O against the real seeded DB.

**Operator must manually validate before shipping:**

```bash
# 1. Point the app at the seeded ufs_data MySQL instance (config/settings.yaml)
# 2. Start:
streamlit run app/main.py
# 3. Log in, select OpenAI LLM in the sidebar
# 4. On Home, ask each of the 3 ship-bar questions:
#    a) "Compare wb_enable across all devices"
#    b) "Which devices have the largest total_raw_device_capacity?"
#    c) "Compare life_time_estimation_a for Samsung vs OPPO devices"
# 5. Confirm for each:
#    - final answer text is non-empty and on-topic
#    - a Plotly chart renders inline
#    - st.expander("Show reasoning") contains run_sql → (pivot_to_wide | normalize_result) → make_chart
#    - no traceback on screen
# 6. Also confirm Explorer, Compare, Settings pages still load without error.
```

## Additional Verification

- README.md mentions agentic / ReAct / tool-calling: **8 occurrences** ✅
- README.md contains zero "SQL preview" / "confirm SQL" / "edit SQL" phrasing ✅
- `logs/queries.log` and `logs/llm.log` both present and populated (85 KB + 100 KB after test run); all lines parse as JSON ✅
- 5 Phase 5 test classes: `ShipBar01WbEnableTest`, `ShipBar02CapacityTest`, `ShipBar03LifetimeBrandCompareTest`, `LogSanityTest`, `SiblingPagesImportTest` — all pass ✅

## REQ-ID Coverage

9/9 Phase 5 requirement IDs covered by the plan:

- SHIP-01/02/03 → `tests/e2e/test_ship_bar.py` ShipBar test classes (mocked DB)
- HOME-05 → `SiblingPagesImportTest` (AST smoke for Explorer/Compare/Settings)
- TEST-01..05 → full suite green + Phase 5 tests respect TEST-05 discipline (no SQL-string assertions)

## Human Verification Items

1. **Live-DB SHIP-01 scenario:** Run "Compare `wb_enable` across all devices" in the browser against seeded `ufs_data`.
   - Expected: per-device table or answer text; bar chart visible; trace shows run_sql → pivot_to_wide → make_chart.
2. **Live-DB SHIP-02 scenario:** Run "Which devices have the largest `total_raw_device_capacity`?".
   - Expected: ranked list; bar chart; trace shows run_sql → normalize_result → make_chart.
3. **Live-DB SHIP-03 scenario:** Run "Compare `life_time_estimation_a` for Samsung vs OPPO devices".
   - Expected: brand-vs-brand comparison; chart; trace shows run_sql → normalize_result → make_chart.
4. **Sibling-page smoke:** Click Explorer, Compare, Settings — each loads and basic interactions work.

## Verdict

**HUMAN_NEEDED.** All automated checks pass (129 tests green, 5 Phase 5 test classes pass, README updated, logs clean). The 3 live-DB ship-bar scenarios require a seeded MySQL instance that this CI environment cannot reach — operator runs the manual validation items above before shipping.
