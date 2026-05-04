# CCXTV2 — System State & Improvement Proposals (Cycle 5 Final)
**Generated:** 2026-05-05 | **Auditor:** DeepSeek v4 — Senior Architect Orchestrator
**Graphify:** 1412 nodes, 4017 edges, 82 communities (+258/+815/+6 vs pre-audit)

---

## Current State Matrix

| Dimension | Pre-Audit | Post-Cycle-5 | Delta |
|:--|:--|:--|:--|
| Architecture docs | 13 fragmented MDs | 7 structured audit docs + 1 executive thesis + 1 critique log | Unified |
| God Nodes mapped | 0 | 10 top + 20 in DNA | Complete |
| Failure points documented | 0 | 16 (10 DNA + 6 Execution) | Complete |
| Golden Rules tested | 0 | 6 immutable thresholds enforced | Locked |
| Test files | 5 | 11 (5 original + 6 v2) | +120% |
| Test functions | ~10 | 134 | +13.4x |
| Test coverage grade | D+ | B | +4 grades |
| Modules audited | 0 | 7 (Hub, Router, Gateway, Guardian, ExecEngine, Viz, Telemetry) | 7 |
| Patches applied | 0 | 3 (PATCH-01, 02, 04) | 3 |
| Patches documented | 0 | 2 more pending (PATCH-03, 05) | 2 |
| SYSTEM_PROMPT | Hardcoded in code | Externalized to skills/SYSTEM_PROMPT.md | Decoupled |
| SeniorAuditOrchestrator | Broken (truncated) | Restored with __init__ + call_action + execute_all_flows | Fixed |
| ZeroDivisionError risk | Present in OpportunityTask | Guarded with price==0 check | Fixed |
| Graphify nodes | 1154 | 1412 | +22% |
| Graphify edges | 3202 | 4017 | +25% |
| Original files preserved | 83+ | 83+ (3 edited, zero deletions) | Intact |

---

## God Nodes Evolution

| Rank | Pre-Audit | Post-Cycle-5 | Delta |
|:--|:--|:--|:--|
| 1 | IntelligenceHub (158e) | IntelligenceHub (168e) | +10 |
| 2 | DataEngine (125e) | DataEngine (125e) | 0 |
| 3 | SFPAdvancedMonitor (91e) | **LiquidityAwareStopLoss (111e)** | +32 (new connections) |
| 4 | AlertMessage (89e) | TelegramService (108e) | — |
| 5 | SentinelGateway (83e) | SFPAdvancedMonitor (101e) | +10 |
| 8 | ExecutionEngine (80e) | ExecutionEngine (90e) | +10 |

**Interpretation:** `LiquidityAwareStopLoss` gained 32 new edges — the execution engine's stop loss is now the #3 most-connected node. Our documentation and tests have created new reference relationships in the graph.

---

## Unused Signal: 4/10 Telemetry Columns

| Column | Logged? | Rendered? | Recommendation |
|:--|:--|:--|:--|
| `vpin_score` | Yes | Scatter + KPI | ✅ Good |
| `slippage_real` | Yes | Timeline + Scatter + KPI | ✅ Good |
| `execution_strategy` | Yes | Pie chart | ✅ Good |
| `symbol` | Yes | Color dimension | ✅ Good |
| `is_high_entropy` | Yes | KPI count | ✅ Good |
| `timestamp` | Yes | X-axis | ✅ Good |
| `obi_delta` | Yes | **NO** | Add: OBI vs Slippage scatter |
| `basis_premium` | Yes | **NO** | Add: Basis overtime line |
| `intended_price` | Yes | **NO** | Add: Price execution delta gauge |
| `final_execution_price` | Yes | **NO** | Add: Price execution delta gauge |

---

## Remaining Improvement Proposals (Thesis-Level)

### IMP-01: Unify DataEngine → IntelligenceHub (CRITICAL)
**Problem:** `ExecutionEngine.estimate_slippage()` creates a new `DataEngine()` per call instead of using the shared `IntelligenceHub` singleton. Bybasses TTL cache, wastes exchange connections. Same code pattern as pre-Hub-migration.
**Fix path:** Replace `DataEngine()` with `hub.get_order_book()` and `hub.get_ticker()` calls. Pass hub reference from Guardian to ExecutionEngine.

### IMP-02: Stub Execution → Real Orders (CRITICAL)
**Problem:** `predatory_execute()` prints but never places orders (lines 51-55 are stubs). IgnitionBridgeTask calls this for $50K Alpha Rotation — no real trade occurs.
**Fix path:** Implement `place_market_order()` using CCXT via Hub's exchange reference. Add flag `EXECUTION_MODE=live|dry` to config.

### IMP-03: VPIN Ambiguity Resolution (HIGH)
**Problem:** `_compute_toxicity` returns `vpin_index=0.0` for both "no data" and "clean market". Impossible to distinguish.
**Fix path:** Return `None` when data fetch fails, add `error_code: str` to `ToxicityResult`. Update all consumers (Router, CurationBuffer, Guardian) to handle `None`.

### IMP-04: Complete to_thread → _internal Refactor (MEDIUM)
**Problem:** `run_intraday_workflow` uses `asyncio.to_thread()` to call `@action` functions, creating duplicate Hub instances.
**Fix path:** Extract `_get_tactical_report_internal` and `_get_udc_internal` from `funding_actions.py` — documented as PATCH-03.

### IMP-05: json.loads(resp.json()) Double-Decode (HIGH)
**Problem:** `LiquidityAwareStopLoss.initialize()` double-decodes the Action Server response. If server returns dict, `json.loads(dict)` raises TypeError → falls to `except` → uses 1% fallback SL silently.
**Fix path:** Check `isinstance(data, str)` before `json.loads()`. Or use `data if isinstance(data, dict) else json.loads(data)`.

### IMP-06: Add obi_delta + basis_premium Charts to Dashboard (LOW)
**Problem:** 4/10 telemetry columns logged but never rendered.
**Fix path:** Add 2 charts: OBI vs Slippage scatter, Basis Premium timeline. 15 lines of Streamlit code.

### IMP-07: Rotate Telemetry JSONL (LOW)
**Problem:** `logs/execution_features.jsonl` grows indefinitely. No rotation, no archiving.
**Fix path:** Add date-based rotation: `execution_features_YYYYMMDD.jsonl`, archive >30 days.

### IMP-08: CurationBuffer Timer Thread Lifecycle (MEDIUM)
**Problem:** Timer callback fires in background thread, checks `self._loop.is_running()` — if loop is stopped, pulse dropped silently.
**Fix path:** Add queue-based retry — if loop not running, queue pulse for next loop start.

---

## Priority Triage

| Priority | # | What | Effort |
|:--|:--|:--|:--|
| **Do now** | IMP-05 | Fix json.loads(resp.json()) double-decode | 5 min, 2 lines |
| **Do now** | IMP-03 | Add error_code to ToxicityResult | 20 min, ~10 lines |
| **Next** | IMP-02 | Implement real order execution | 2 hr, new method |
| **Next** | IMP-01 | Unify DataEngine → Hub in ExecutionEngine | 1 hr, refactor |
| **Soon** | IMP-04 | Complete _internal refactor | 1 hr, extract helpers |
| **Later** | IMP-06 | Add dashboard charts | 30 min, Streamlit |
| **Later** | IMP-08 | Fix CurationBuffer thread lifecycle | 1 hr, queue |
| **Eventually** | IMP-07 | Rotate telemetry JSONL | 20 min |

---

## Cycle 5 Artifacts Index

```
project_dna_v2.json                          # SSoT — 9 layers, 11 flows, 16 failure points
skills/SYSTEM_PROMPT.md                      # Externalized LLM prompt (editable without code)

docs/architecture_v2/
  01_MICROSTRUCTURAL_AUDIT.md                # 10 functions with decision matrices
  02_CONFLUENCE_FLOWS.md                     # 4 data flow diagrams, signal maps
  03_EXECUTIVE_THESIS.md                     # 7 module summaries, system grade B+
  04_CRITIQUE_LOG.md                         # 7 bearish divergences
  05_VISUALIZATION_LAYER_AUDIT.md            # 4 viz/telemetry modules audited
  05_PATCHES_PENDIENTES.md                   # 5 patches with before/after code
  06_EXECUTION_ENGINE_AUDIT.md               # 4 functions, 6 failure modes
  audit_summary.json                         # Structured audit state

tests/v2/
  test_hub_invalidation.py                   # 26 tests — VPIN, Basis, CVD, Z-Score
  test_signal_propagation.py                 # 39 tests — Router, VPIN gates, cooldowns
  test_malformed_inputs.py                   # 32 tests — injection, null, boundaries
  test_visualization_layer.py                # 15 tests — telemetry, theme, charts
  test_action_server_smoke.py                # 7 tests — health, endpoints, deadlock
  test_execution_engine.py                   # 22 tests — trailing stop, SL, slippage
```

**Zero original files deleted. 3 files minimally edited (Guardian_Daemon.py, senior_audit_orchestrator.py, auto_senior_analyst.py).**
