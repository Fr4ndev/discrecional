# Tier-2: Confluence Analysis — Cross-Module Data Flows & Dependencies
**Generated:** 2026-05-04 | **Source:** project_dna_v2.json + graphify community clustering

---

## FLOW-01: `Exchange → IntelligenceHub → TTL Cache → All Consumers`

```
┌──────────────┐     CCXT REST/WS     ┌──────────────────────┐
│  Hyperliquid  │ ──────────────────► │  IntelligenceHub     │
│  (Exchange)   │   OHLCV, OB,        │  (Singleton)         │
│               │   Trades, Ticker    │                      │
└──────────────┘                      │  ┌────────────────┐  │
                                      │  │  _TTLCache     │  │
                                      │  │  (15s default) │  │
                                      │  └───────┬────────┘  │
                                      │          │            │
                                      │  ┌───────▼────────┐  │
                                      │  │  ZScoreEngine   │  │
                                      │  │  FundingEngine  │  │
                                      │  │  CVD velocity   │  │
                                      │  └───────┬────────┘  │
                                      └──────────┼───────────┘
                                                 │
                    ┌────────────────────────────┼────────────────────────────┐
                    │                            │                            │
           ┌────────▼────────┐          ┌────────▼────────┐         ┌────────▼────────┐
           │ Guardian_Daemon │          │  Action Server   │         │  Hub Reader     │
           │ (9 sentinels)   │          │  (40+ endpoints) │         │  (standard API) │
           └────────┬────────┘          └────────┬────────┘         └────────┬────────┘
                    │                            │                            │
                    ▼                            ▼                            ▼
            SignalBus + Gateway          auto_senior_analyst            daemons/*
            → ReactiveRouter            → DeepSeek → Dossiers          (ICT, SFP, LevelBreak)
            → Telegram Alerts
```

| Step | Module | Data | Protocol | Criticality | Failure Mode |
|:--|:--|:--|:--|:--|:--|
| 1 | CCXT Exchange | OHLCV, OB, Trades, Ticker | REST/WS | CRITICAL | Connection loss → 60s cooldown → all modules stall |
| 2 | IntelligenceHub | MarketSnapshot | Async coroutine (gather) | CRITICAL | 429 RateLimit → cooldown → None cascade |
| 3 | _TTLCache | Cached OHLCV/OB/Trades | In-memory dict + asyncio.Lock | HIGH | Stale data (15s) → outdated signals |
| 4 | Guardian_Daemon | Per-cycle scans (10-30s polls) | asyncio.create_task | CRITICAL | Hub failure → task crash → auto-restart |
| 5 | Action Server | Fresh Hub instance per call | _run_hub_sync (new_event_loop) | CRITICAL | **Event loop nesting → DEADLOCK (FP-01)** |
| 6 | Hub Reader | Live metrics via get_live_metrics() | Async accessor | MEDIUM | No cache → redundant Hub calls |

---

## FLOW-02: `Guardian Signal Pipeline → Curation Buffer → Telegram`

```
Guardian Daemon
    │
    ├── IgnitionBridgeTask._cycle()
    │       └── _execute_rotation() → dispatch_enriched_alert("whale", ...)
    │
    ├── WhaleMonitorTask._process_completed_block()
    │       └── dispatch_enriched_alert("whale", ...)
    │
    ├── SqueezeMonitorTask._cycle()
    │       └── alert("squeeze_hc", priority=1)
    │
    ├── SpoofDetectorTask._cycle()
    │       └── SignalBus.publish(Signal("SPOOF", ...)) → alert("spoof_*", priority=2)
    │
    ├── SFPSentinelTask → SFPAdvancedMonitor.run()
    │       └── alert("sfp_*", priority=1/2)
    │
    ├── LevelBreakTask._cycle()
    │       └── alert("break_*", priority=2) / alert("prox_*", priority=3)
    │
    ├── OpportunityTask._scan_asset()
    │       └── alert("senior_bull/bear_*", priority=2)
    │
    ├── StrategicAuditTask._cycle() [hourly]
    │       └── subprocess: strategies/zscore_chart.py
    │
    └── SeniorAuditTask._cycle() [hourly]
            └── subprocess: auto_senior_analyst.py --mode full

                           │
                           ▼
    ┌──────────────────────────────────────────────┐
    │  SentinelGateway (Singleton)                 │
    │                                              │
    │  AlertMessage.dispatch()                     │
    │  ├── Deduplication (cooldown 600s)           │
    │  ├── Rate Limiting (max 10/min)              │
    │  ├── Priority Queue (CRITICAL first)         │
    │  └── _send() → LOCAL-ONLY log (Telegram OFF) │
    │                                              │
    │  CurationBuffer (30s window)                 │
    │  ├── ingest(AlertSignal)                     │
    │  ├── _reset_timer() → threading.Timer        │
    │  ├── _flush() → _synthesize()                │
    │  │   └── VPIN gate → signal weighting        │
    │  └── dispatch_synthetic(pulse_text)           │
    └──────────────────────────────────────────────┘
                           │
                           ▼
    ┌──────────────────────────────────────────────┐
    │  TelegramService / Gateway._send()           │
    │  CURRENTLY: LOCAL-ONLY (no Telegram send)    │
    │  Format: Markdown with priority icons        │
    └──────────────────────────────────────────────┘
```

| Signal Source | Signal Type | Priority | Dedup Window | Curation Weight | VPIN Gate |
|:--|:--|:--|:--|:--|:--|
| IgnitionBridge (rotation) | whale | 1 (CRITICAL) | 3600s | 3 | N/A (direct) |
| IgnitionBridge (resurgence) | whale | 2 (HIGH) | 600s | 3 | N/A (direct) |
| SqueezeMonitor (3/3) | whale | 1 (CRITICAL) | 1800s | 3 | N/A (direct) |
| SqueezeMonitor (2/3) | whale | 3 (MEDIUM) | 600s | 3 | N/A (direct) |
| SpoofDetector | spoofing | 2 (HIGH) | 60s per symbol | 1 | Via SignalBus |
| WhaleMonitor (direct) | whale | 1 (CRITICAL) | 30s block_id | 3 | N/A |
| WhaleMonitor (curation) | whale | — | 30s buffer | 3 | Via CurationBuffer |
| SFPSentinel | sfp | 1-2 | 600s | 2 | Via legacy monitor |
| LevelBreak | level_break | 2 (HIGH) | 600s | 2 | N/A |
| LevelBreak (proximity) | level_break | 3 (MEDIUM) | 1200s | 1 | N/A |
| OpportunityTask (fusion) | sfp | 2 (HIGH) | 600s | 2 | Via SignalBus |
| SeniorAudit (hourly) | — | 2 (HIGH) | 3600s | — | DeepSeek |
| StrategicAudit (hourly) | — | — (suppressed) | — | — | Background |

---

## FLOW-03: `Controller (Telegram Bot) → Routine Execution → Reporting`

```
┌─────────────────────────────────────────────────────────────┐
│  controller.py (Telegram Bot)                               │
│                                                             │
│  cmd_flow_generic()                                         │
│  ├── /turbo, /sfp, /scalp, /intraday, /swing, /alpha       │
│  ├── /omega, /ignition, /ele_audit, /decision_matrix        │
│  └── /full_audit                                            │
│                                                             │
│  RoutineBridge.run_routine(routine, use_ai=False)           │
│  ├── Map → ModeMap[{routine}→{mode}]                        │
│  ├── Execute: python3 auto_senior_analyst.py --mode {mode} │
│  ├── Parse stdout (between ==== delimiters)                 │
│  ├── Fallback: latest Dossier_*.md in reports_history/      │
│  └── Return: verdict string (Markdown, ≤4000 chars)        │
│                                                             │
│  cmd_analysis()                                             │
│  └── core/ai_analyst.analyze(profile, use_ai)              │
│                                                             │
│  cmd_status()                                               │
│  └── core/reactive_router.get_router()._last_run            │
└─────────────────────────────────────────────────────────────┘

                         │ (on-demand flows)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  auto_senior_analyst.py                                     │
│                                                             │
│  MODES: omega, scalp, intraday, swing, sfp, full           │
│                                                             │
│  Flow definition → ActionClient.flow_*()                    │
│  ├── flow_scalp:    tox + micro per asset                  │
│  ├── flow_intraday: basis + UDC + tactical                 │
│  ├── flow_swing:    full_snapshot + tactical_swing         │
│  ├── flow_alpha:    sfp_triggers + ele_audit               │
│  └── flow_ob_walls: ob-walls per asset                     │
│                                                             │
│  Results → save_raw(AUDIT_RUNS_DIR)                        │
│  Skills → load_skills(max_chars=4000)                       │
│  Prompt → build_user_prompt(data, skills)                   │
│  DeepSeek → call_deepseek(prompt) [temperature=0.1]         │
│  Report → save_report(Dossier_{MODE}_{ts}.md)               │
└─────────────────────────────────────────────────────────────┘

                         │ (fallback path)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  core/ai_analyst.py                                         │
│  └── get_analyst().analyze(profile, use_ai=False)          │
│      └── Deterministic analysis (no LLM)                    │
└─────────────────────────────────────────────────────────────┘

                         │ (legacy bash path)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  scripts/ops/run_flows.sh {flow}                             │
│  scripts/routines/run_scalp_workflow.sh                      │
│  scripts/routines/run_intraday_workflow.sh                   │
│  scripts/routines/run_sfp_routine.sh                         │
│  scripts/routines/run_ele_routine.sh                         │
│  scripts/routines/run_full_audit.sh                          │
│  scripts/ignite_omega.sh                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## FLOW-04: `Action Server Composite Workflows (Deadlock Risk Area)`

```
┌─────────────────────────────────────────────────────────────┐
│  Action Server (sema4ai/actions, port 8080)                 │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  audit_actions.py                                    │   │
│  │                                                      │   │
│  │  @action run_scalp_workflow(assets)                   │   │
│  │  └── _run_hub_sync(_routine)                         │   │
│  │      └── _routine(hub):                              │   │
│  │          ├── _get_toxicity_index_internal(hub, ...)   │   │
│  │          ├── _microstructure_audit_internal(hub, ...) │   │
│  │          └── _get_ob_walls_internal(hub, ...)         │   │
│  │                                                      │   │
│  │  ⚠️ FIXED: Using _internal async helpers directly    │   │
│  │  ✅ NOT calling @action → no nested _run_hub_sync    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  run_intraday_workflow(assets)                       │   │
│  │  └── _routine(hub):                                 │   │
│  │      ├── _get_basis_internal(hub, ...)               │   │
│  │      ├── asyncio.to_thread(get_tactical_report) [⚠️] │   │
│  │      └── asyncio.to_thread(get_ultra_deep_confluence)│   │
│  │                                                      │   │
│  │  ⚠️ NOTE: to_thread calls @action functions —        │   │
│  │     these create their own _run_hub_sync loops       │   │
│  │     via thread executor (safe from deadlock,         │   │
│  │     but creates multiple Hub instances)              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Deadlock mechanism (FP-01):                                │
│    @action A → _run_hub_sync → new_event_loop →             │
│    calls @action B → _run_hub_sync → new_event_loop #2 →   │
│    both loops try to acquire Hub._semaphore →               │
│    loop #1 blocks on loop #2 → DEADLOCK                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Dependency Matrix (Cross-Community)

| From Community | To Community | Edge Count | Primary Files | Risk |
|:--|:--|:--|:--|:--|
| C1 (Core Orchestration) | C5 (Action Server Actions) | 66 | data_engine.py ↔ Core_Intelligence_Hub.py | HIGH — all action endpoints depend on Hub |
| C0 (Strategy Suite) | C2 (Support/Monitoring) | 60 | config.py ↔ funding_monitor.py | MEDIUM |
| C0 (Strategy Suite) | C1 (Core Orchestration) | 53 | config.py ↔ data_engine.py | HIGH — Strategy engines need Hub data |
| C1 (Core Orchestration) | C3 (Hub Pipeline) | 48 | data_engine.py ↔ Core_Intelligence_Hub.py | HIGH — internal coupling |
| C0 (Strategy Suite) | C5 (Action Server) | 47 | config.py ↔ Core_Intelligence_Hub.py | HIGH — shared types |
| C1 (Core Orchestration) | C2 (Support/Monitoring) | 41 | data_engine.py ↔ funding_monitor.py | MEDIUM |
| C1 (Core Orchestration) | C10 (ICT Sentinel) | 35 | data_engine.py ↔ ict_v16_sentinel.py | MEDIUM — legacy sentinel |

---

## Signal Type → Flow Execution Map

```
Signal Type         →   Flow            VPIN Gate    Cooldown    Script
─────────────────────────────────────────────────────────────────────────
levelbreak          →   intraday        0.62         300s        run_flows.sh intraday
strategicaudit      →   intraday        0.62         300s        run_flows.sh intraday
ict_v16_4h          →   turbo           0.62         120s        run_flows.sh turbo
ict                 →   turbo           0.62         120s        run_flows.sh turbo
sfp_v2              →   sfp             0.55         180s        run_flows.sh sfp
sfp                 →   sfp             0.55         180s        run_flows.sh sfp
whalemonitor        →   scalp           0.50          60s        run_flows.sh scalp
squeezemonitor      →   scalp           0.50          60s        run_flows.sh scalp
ignitionbridge      →   turbo           0.62         120s        run_flows.sh turbo
spoofdetector       →   scalp           0.50          60s        run_flows.sh scalp
omega (manual)      →   omega           0.62         600s        ignite_omega.sh
```
