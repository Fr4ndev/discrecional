# Tier-1: Microstructural Audit — Decision Matrices per Critical Function
**Generated:** 2026-05-04 | **Source:** graphify-out/graph.json (1154 nodes, 3202 edges, 76 communities)
**Context:** Institutional Crypto Trading Intelligence Hub — PhD-Level Microstructure Analysis

---

## MF-01: `IntelligenceHub._compute_toxicity(symbol, ob_depth=50, trade_limit=500) → ToxicityResult`

| Dimension | Value |
|:--|:--|
| **Design Intent** | Composite VPIN proxy blending OBI volume imbalance (40%) with trade-flow toxicity (60%). Implements Easley et al. VPIN via volume clock proxy for informed-vs-noise classification. |
| **State Transitions** | 1. `_fetch_order_book(symbol, ob_depth)` → bids/asks total → OBI<br>2. `_fetch_trades(symbol, trade_limit)` → buy_vol, sell_vol → imbalance → |buy-sell|/total<br>3. VPIN = 0.60 × trade_imbalance + 0.40 × |OBI|<br>4. Absorption = top_5_bids / total_bids (iceberg proxy)<br>5. Senior verdict: INFORMED_FLOW (>0.70 & abs>0.60), ELEVATED_ACTIVITY (>0.40), CLEAN_FLOW (else) |
| **Invalidation Levels** | • Both OB **and** trades fetch fail → vpin_index=0.0, absorption_rate=0.0 (indistinguishable from actual low toxicity)<br>• total_vol ≤ 0 (no trades) → vpin_index=0.0<br>• bids_tot = 0 (empty OB) → absorption_rate=0.0<br>• 429 RateLimit → 60s cooldown → all subsequent calls return None → cascade |
| **Dependencies** | `_fetch_order_book` (TTL 6s), `_fetch_trades` (TTL 8s), both behind `_retry` wrapper (3 retries, exp backoff, semaphore=15) |
| **Invariants** | `0.0 ≤ vpin_index ≤ 1.0`, `0.0 ≤ absorption_rate ≤ 1.0`, `-1.0 ≤ obi_current ≤ 1.0` |
| **Failure Modes** | **FP-03 (HIGH):** Returns vpin=0 when data fails → falsely blocks ALL flow execution (gate = 0.62). **Fix:** return None or raise to distinguish "no data" from "low toxicity" |
| **Golden Rules Applied** | VPIN_THRESHOLD=0.62 → `is_scalp_valid`, ABSORPTION_GATE=0.60 → `senior_verdict` |

---

## MF-02: `IntelligenceHub._compute_basis(symbol_perp, symbol_spot) → Optional[BasisSnapshot]`

| Dimension | Value |
|:--|:--|
| **Design Intent** | Spot-vs-Perpetual basis divergence detection. Negative basis = Spot Premium = institutional accumulation stealth. Positive = Perp FOMO/hedging. |
| **State Transitions** | 1. `_fetch_ohlcv_spot(spot, "1m", 2)` → spot_close<br>2. `_fetch_ohlcv(perp, "1m", 2)` → perp_close<br>3. basis_usd = perp - spot<br>4. basis_pct = (basis_usd / spot) × 100<br>5. interpretation: "Spot Premium" if < 0, "Perp Premium" if ≥ 0<br>6. `is_spot_premium` = basis_pct < BASIS_THRESHOLD_PCT (-0.05) |
| **Invalidation Levels** | • `_spot_exchange is None` → returns None<br>• Either spot_df or perp_df is None/empty → returns None<br>• spot_price = 0 → basis_pct = 0.0 (silent) |
| **Dependencies** | `_fetch_ohlcv_spot` (uses separate spot Exchange), `_fetch_ohlcv` (perp), both behind retry wrapper |
| **Invariants** | Return is `Optional[BasisSnapshot]` — consumers MUST handle None<br>`is_spot_premium` → True only when basis_pct < -0.05 |
| **Failure Modes** | Spot exchange init fails (non-fatal) → `_spot_exchange=None` → all basis calls return None. System operates without basis context — degrades intraday/swing verdicts |

---

## MF-03: `IntelligenceHub._compute_cvd_state(symbol, trade_limit=200) → Optional[CVDState]`

| Dimension | Value |
|:--|:--|
| **Design Intent** | CVD (Cumulative Volume Delta) velocity and acceleration detection. CVD'' > 0 + OBI < 0 = "Dynamic Absorption" (God Candle ignition). CVD'' < 0 + OBI > 0 = exhaustion. |
| **State Transitions** | 1. Fetch 2×trade_limit trades (400 max)<br>2. Split into two halves, compute CVD1, CVD2<br>3. velocity = CVD2 - CVD1<br>4. acceleration = velocity - prev_velocity (per-symbol stored in `_cvd_velocity` dict)<br>5. Verdict: IGNITION_ACCELERATING / DECAYING_MOMENTUM / SHORT_SQUEEZE_ABSORPTION / STABLE |
| **Invalidation Levels** | • trades_df None or len < trade_limit → returns None<br>• First call (no prev_velocity) → accel = velocity (effectively a ramp-up signal)<br>• `_cvd_velocity` dict is **in-memory only** — lost on restart |
| **Dependencies** | `_fetch_trades(symbol, trade_limit*2)` (TTL 8s), per-symbol state in `_cvd_velocity: Dict[str, float]` |
| **Invariants** | `is_aggression_confirmed` = acceleration > CVD_ACCEL_GATE (0.0) |
| **Failure Modes** | Trades fetch fail → returns None → Guardian/consumer skips CVD analysis. State lost on crash = ramp-up signals on restart |

---

## MF-04: `IntelligenceHub.market_snapshot(symbol_perp, symbol_spot, ob_depth=50, trade_limit=300) → MarketSnapshot`

| Dimension | Value |
|:--|:--|
| **Design Intent** | Composite atomic snapshot — fires OBI, CVD, Toxicity, Funding, Ticker, and optionally Basis in parallel via `asyncio.gather`. Primary method Guardian_Daemon calls every cycle. |
| **State Transitions** | 1. Build task list: obi, cvd, toxicity, funding, ticker [+ basis if spot]<br>2. `asyncio.gather(*tasks)` — all independent, concurrent<br>3. Extract price from ticker (fallback 0.0)<br>4. Return `MarketSnapshot` dataclass (all fields typed) |
| **Invalidation Levels** | • Individual fetches fail → their field is None or default (OBI=0, CVD=None, Toxicity=VPIN=0, Funding=None, Basis=None)<br>• Ticker fetch fails → price = 0.0 → downstream price-dependent logic breaks<br>• No aggregate error — partial snapshots are silently incomplete |
| **Dependencies** | `_compute_obi`, `_compute_cvd_state`, `_compute_toxicity`, `_compute_funding_state`, `_fetch_ticker`, `_compute_basis` (all private) |
| **Invariants** | Price field is always float (defaults to 0.0 on failure)<br>All sub-fields support None for optional states |
| **Failure Modes** | 429 cooldown → ALL concurrent fetches fail → MarketSnapshot with all None/defaults → Guardian skips cycle → no signals |

---

## MF-05: `ReactiveRouter.on_signal(trigger: RouterTrigger) → Optional[str]`

| Dimension | Value |
|:--|:--|
| **Design Intent** | Signal → Flow mapping engine. Guardian publishes signal → Router resolves flow name → checks cooldown → checks VPIN gate → executes bash script. Implements institutional rate-limiting and toxicity gating. |
| **State Transitions** | 1. `_resolve_flow(trigger)` → exact/partial match in SIGNAL_FLOW_MAP<br>2. `_check_cooldown(flow)` → `time.time() - last[flow] > FLOW_COOLDOWN[flow]`<br>3. `_check_vpin_gate(flow, trigger.vpin)` → `vpin >= FLOW_VPIN_GATE[flow]`<br>4. `_update_cooldown(flow)`<br>5. `_run_flow(flow, trigger)` → `subprocess_exec bash scripts/ops/run_flows.sh {flow}` (120s timeout) |
| **Invalidation Levels** | • Signal type not in SIGNAL_FLOW_MAP → returns None (silent, not an error)<br>• VPIN below gate → logged, returns None (expected behavior)<br>• Flow in cooldown → logged DEBUG, returns None<br>• Bash script error → logged ERROR, no retry<br>• Process timeout (120s) → logged ERROR |
| **Dependencies** | `asyncio.create_subprocess_exec`, `scripts/ops/run_flows.sh`, `scripts/ignite_omega.sh`, `Core_Intelligence_Hub.VPIN_THRESHOLD` |
| **Invariants** | `_lock` (asyncio.Lock) serializes all signal processing<br>Cooldowns are in-memory — lost on restart |
| **Failure Modes** | Flow scripts crash → Router continues (next signal processed). Cooldown prevents rapid re-execution. No dead-letter queue for failed flows. |

---

## MF-06: `CurationBuffer._synthesize(signals: List[AlertSignal]) → str`

| Dimension | Value |
|:--|:--|
| **Design Intent** | 30-second aggregation window that fuses multiple raw Guardian signals into a single Unified Alpha Pulse. Applies Golden Rule gates (VPIN, Basis, OBI) before broadcasting. Implements confluence scoring with weighted signal types. |
| **State Transitions** | 1. Ingest signals for 30s (timer resets on each new signal)<br>2. Flush: take latest `AlertSignal` for metric context (VPIN, Basis, OBI)<br>3. **GATE:** VPIN < 0.62 → block pulse (silent, logged)<br>4. Score: sum `SIGNAL_WEIGHTS[signal_type]` across all signals<br>5. Probability: score≥7=MUY_ALTA, ≥4=ALTA, ≥2=MODERADA, else BAJA<br>6. Assemble Markdown pulse with regime, z-score, basis/obi context |
| **Invalidation Levels** | • **FP-08 (MEDIUM):** Timer-based flushing — if the timer fires while a signal is being ingested, race condition possible. Thread safety depends on `threading.Lock`.<br>• VPIN < 0.62 → entire pulse suppressed (all signals lost, not queued)<br>• Empty buffer at flush → no pulse (normal)<br>• Missing metrics (VPIN=0, Basis=0) → still generates pulse without context |
| **Dependencies** | `AlertSignal` payload (from Hub via `dispatch_enriched_alert`), `threading.Timer`, `threading.Lock`, Golden Rules from `core/Core_Intelligence_Hub` |
| **Invariants** | Max 30s latency from first signal to pulse<br>VPIN gate is absolute — pulse blocked if VPIN < threshold regardless of signal count |
| **Failure Modes** | Timer thread crash → buffer accumulates forever → no pulses emitted. High-frequency signals → buffer may overshoot before timer fires. |

---

## MF-07: `GuardianDaemon.run() → supervision loop`

| Dimension | Value |
|:--|:--|
| **Design Intent** | Process-level master orchestrator. One shared IntelligenceHub connection for all 9 sentinel tasks. Auto-restart crashed tasks with cooldown. Heartbeat every 60 cycles. Kill-switch via `data/STOP_ALL.lock`. |
| **State Transitions** | 1. Hub connect → Gateway start (queued mode) → SignalBus bridge → Launch all sentinel Tasks<br>2. Supervisor loop (every 10s): check kill-switch → check crashed tasks → restart if needed<br>3. Heartbeat (every 60 cycles): write `guardian_hbeat.json`<br>4. Shutdown: stop sentinels → cancel tasks → stop gateway → close Hub |
| **Invalidation Levels** | • `data/STOP_ALL.lock` exists → immediate shutdown<br>• Hub.connect() fails → exception raised, Guardian crashes<br>• Task exception → caught, logged, task restarted after 10s delay<br>• SIGINT/SIGTERM → graceful shutdown |
| **Dependencies** | `IntelligenceHub` singleton, `SentinelGateway` singleton, `SignalBus` singleton, all 9 sentinel classes, `watchlist_levels.json`, external scripts |
| **Invariants** | All tasks share ONE Hub instance (connection pooling via semaphore=15)<br>Gateway in queued mode only under Guardian |
| **Failure Modes** | **FP-02 (CRITICAL):** Hub exchange connection loss → all sentinels get None/null → no alerts. Hub cooldown 60s → silent gap. Kill-switch provides manual override. |

---

## MF-08: `auto_senior_analyst.ActionClient.flow_*()` → composite data capture

| Dimension | Value |
|:--|:--|
| **Design Intent** | HTTP client that calls Action Server endpoints to capture real-time market data, then feeds it to DeepSeek API for institutional dossier generation. Each flow method chains multiple endpoint calls per asset. |
| **State Transitions** | 1. `flow_scalp()`: POST get-toxicity-index + POST microstructure-audit per asset (BTC, ETH)<br>2. `flow_intraday()`: POST get-basis per asset + POST UDC + POST tactical-scalp<br>3. `flow_swing()`: POST full-snapshot + POST tactical-swing<br>4. `flow_alpha()`: POST detect-confluence-trigger + POST eth-ele-audit<br>5. `flow_ob_walls()`: POST get-ob-walls per asset<br>6. All results stored in `self.results` dict → saved to `data/audit_runs/` |
| **Invalidation Levels** | • Server timeout (90s) → endpoint returns None → partial data<br>• HTTP !200 → logged WARNING, returns None (non-fatal)<br>• JSON decode error on response → raw string kept<br>• All endpoints fail → `len(ac.results) == 0` → sys.exit(1) |
| **Dependencies** | Action Server (localhost:8080), httpx.AsyncClient (90s timeout), data/audit_runs/ for persistence |
| **Invariants** | Sequential calls with 1s breathing room between flows<br>Results dict keys: `tox_BTC`, `micro_BTC`, `basis_BTC`, `udc`, `tactical_scalp`, `sfp_triggers`, `ele_audit`, etc. |
| **Failure Modes** | **FP-07 (MEDIUM):** Server down → fallback to `manage.sh start` + 90s bootstrap wait. DeepSeek unavailable → deterministic fallback report with raw JSON. |

---

## MF-09: `controller.RoutineBridge.run_routine(routine, use_ai) → str`

| Dimension | Value |
|:--|:--|
| **Design Intent** | Telegram command → analysis pipeline bridge. Routes /omega, /scalp, /intraday, /sfp etc. to either auto_senior_analyst.py (DeepSeek) or bash scripts + ai_analyst.py (deterministic). Manages Action Server lifecycle (start → execute → stop). |
| **State Transitions** | 1. Map routine name to mode → execute `auto_senior_analyst.py --mode {mode}`<br>2. Parse stdout for verdict (between `====` delimiters)<br>3. Fallback: latest `reports_history/Dossier_*.md` file<br>4. Document: write to `reports_history/analisis_{routine}_{ts}.md` |
| **Invalidation Levels** | • auto_senior_analyst fails → checks `reports_history/` for latest report<br>• No verdict found → returns error string<br>• Action Server start fails → returns "Abortando rutina" error<br>• Bash script error → returns stderr to user<br>• Verdict > 4000 chars → chunked Telegram send (4 parts max, 0.5s delay) |
| **Dependencies** | auto_senior_analyst.py, Action Server (localhost:8080), bash scripts, reports_history/, core/ai_analyst |
| **Invariants** | Server lifecycle: start → poll (15 × 2s = 30s max) → execute → stop<br>All reports saved to reports_history/ |
| **Failure Modes** | Port 8080 occupied → `fuser -k 8080/tcp` cleanup before start. Server start timeout (30s) → routine aborted. |

---

## MF-10: `IgnitionBridgeTask._cycle()` → Alpha Rotation Protocol

| Dimension | Value |
|:--|:--|
| **Design Intent** | BTC→ETH Alpha Rotation detector (Section 6, FLOWS_OPERATING_MANUAL). Monitors BTC consolidation + ETH readiness for capital rotation execution. Triggers predatory execution with liquidity-aware stop-loss. |
| **State Transitions** | 1. `hub.ignition_check(BTC, ETH)` → returns phase + metrics<br>2. STEALTH → no action (noise suppression)<br>3. ALPHA_ROTATION_TRIGGERED → cooldown check → `_execute_rotation()`<br>4. BTC_RESURGENCE → alert (pause ETH entry)<br>5. Execution: LiquidityAwareStopLoss + ExecutionEngine.predatory_execute (TWAP if slippage) |
| **Invalidation Levels** | • Cooldown: max 1 rotation per hour (self._trigger_cooldown=3600s)<br>• DRY_RUN=1 → no actual execution, just alerts<br>• SL initialization fails → alert still sent without SL price<br>• BTC re-ignites (VPIN > 0.70) → rotation PAUSED, alert sent |
| **Dependencies** | `IntelligenceHub.ignition_check()`, `ExecutionEngine`, `LiquidityAwareStopLoss`, `SentinelGateway` |
| **Invariants** | Rotation only at ALPHA_ROTATION_TRIGGERED phase<br>Execution size: 50,000 USD<br>Alert priority: 1 (CRITICAL) with dedup key "alpha_rotation" |
| **Failure Modes** | Hub ignition_check partial failure → returns default NEUTRAL → no rotation triggered (false negative). Execution price stale → slippage impact. |

---

## Golden Rules Reference (sourced from code, not docs)

| Rule | Value | Source | Enforced At |
|:--|:--|:--|:--|
| VPIN_THRESHOLD | 0.62 | `core/Core_Intelligence_Hub.py:L52` | `is_scalp_valid`, `CurationBuffer._synthesize`, `ReactiveRouter._check_vpin_gate` |
| BASIS_THRESHOLD_PCT | -0.05 | `core/Core_Intelligence_Hub.py:L53` | `BasisSnapshot.is_spot_premium`, `CurationBuffer._synthesize` |
| CVD_ACCEL_GATE | 0.0 | `core/Core_Intelligence_Hub.py:L54` | `CVDState.is_aggression_confirmed`, `IgnitionBridgeTask` |
| OBI_IGNITION | 0.40 | `core/Core_Intelligence_Hub.py:L55` | `IntelligenceHub.ignition_check()` |
| OBI_SCALP_GATE | 0.40 | `core/Core_Intelligence_Hub.py:L56` | `microstructure_audit` verdict logic |
| ABSORPTION_GATE | 0.60 | `core/Core_Intelligence_Hub.py:L57` | `_compute_toxicity` senior_verdict |
