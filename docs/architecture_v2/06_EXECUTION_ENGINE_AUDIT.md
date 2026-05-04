# Execution Engine Audit — CCXTV2 Cycle 5
**Module:** `core/execution_engine.py` (131 lines, God Node #8, 80 edges)

---

## MF-15: `ExecutionEngine.estimate_slippage(symbol, side, amount_usd) → float`

| Dimension | Value |
|:--|:--|
| **Design Intent** | Order-book-walk slippage estimator. Walks 100-level order book accumulating liquidity until order is filled. Returns slippage as `|avg_fill - mid| / mid`. |
| **State Transitions** | 1. Create fresh `DataEngine()` (NOT shared Hub) → connect → fetch OB + ticker<br>2. Walk OB levels (asks for buy, bids for sell)<br>3. Accumulate USD until `amount_usd` filled<br>4. `avg_price = filled_usd / accumulated_qty`<br>5. `slippage = |avg_price - mid| / mid`<br>6. Close DataEngine connection |
| **Invalidation Levels** | • OB depth insufficient → `filled_usd < amount_usd` → returns `1.0` (infinite slippage)<br>• `ticker['last']` missing → KeyError crash<br>• `accumulated_qty = 0` → ZeroDivisionError at `avg_price` calculation<br>• OB empty (`[]`) → loop skips, `filled_usd=0` → returns 1.0 |
| **Dependencies** | `core/data_engine.DataEngine` (creates NEW instance per call — bypasses shared Hub + TTL cache) |
| **Failure Modes** | Fresh DataEngine per call = no TTL cache benefit, redundant exchange connections. Returns `1.0` as sentinel for "no liquidity" — consumer treats this as infinite slippage. |

---

## MF-16: `ExecutionEngine.predatory_execute(symbol, side, total_amount_usd) → None`

| Dimension | Value |
|:--|:--|
| **Design Intent** | Adaptive execution router: Market order if slippage ≤ 0.15%, Micro-TWAP (5 fragments) if higher. |
| **State Transitions** | 1. `estimate_slippage(symbol, side, total_amount_usd)`<br>2. If `slip > slip_threshold(0.0015)` → print warning → loop 5 fragments × 0.5s spacing<br>3. Else → print "Liquidity Optimal" → single market order<br>4. **Actual order execution is stubbed** (commented `# await self.place_market_order(...)`) |
| **Invalidation Levels** | • No actual execution — prints only. Used in dry mode or pending implementation.<br>• `estimate_slippage` failure → slip=1.0 → TWAP path (conservative approach) |
| **Dependencies** | `self.estimate_slippage`, `asyncio.sleep(0.5)` |
| **Failure Modes** | **Stub execution** — called by `IgnitionBridgeTask._execute_rotation()` in Guardian. Prints to stdout but no order reaches exchange. DRY_RUN guard exists upstream (Guardian line 182). |

---

## MF-17: `DynamicTrailingStop.update(current_price) → str`

| Dimension | Value |
|:--|:--|
| **Design Intent** | Activation-based trailing stop. Activates when price ≥ activation_price, then trails peak by `trail_pct` (default 0.5%). Returns "EXIT_NOW" when breached. |
| **State Transitions** | 1. Not active + `current_price >= activation_price` → activate, set peak<br>2. Active: update peak if higher, compute `stop = peak × (1 - trail_pct)`<br>3. `current_price <= stop` → "EXIT_NOW"<br>4. Else → "HOLD" |
| **Invalidation Levels** | • Only trails LONG positions (price goes up). No SHORT trailing stop logic.<br>• `peak_price` defaults to 0 — if activation_price = 0, activates immediately<br>• No ATR-based volatility adjustment |
| **Dependencies** | None (pure math) |
| **Failure Modes** | Single-direction only. In bearish market, no protection. peak_price resets to 0 on init — if used for short, stop would be at negative price (never triggers). |

---

## MF-18: `LiquidityAwareStopLoss.initialize() → None`

| Dimension | Value |
|:--|:--|
| **Design Intent** | Fetches Ultra-Deep Confluence walls from Action Server to find nearest institutional support. Sets SL 2 ticks below nearest wall. Expands SL by 15% if toxicity > 0.70. |
| **State Transitions** | 1. HTTP POST `get-ultra-deep-confluence/run` to Action Server<br>2. Parse `data["top_supports_bids"]` → nearest wall price<br>3. `sl_price = nearest_wall - 2` (tick offset)<br>4. If `tox_index > 0.70` → expand SL by 15%<br>5. Fallback: `sl_price = entry_price * 0.99` (1% fixed) |
| **Invalidation Levels** | • **Bug risk:** `json.loads(resp.json())` — if Action Server returns already-parsed JSON, `resp.json()` returns dict, `json.loads(dict)` raises TypeError → falls to except → 1% fallback<br>• `top_supports_bids` key may not exist → falls to except → 1% fallback<br>• `supports[0]` may be empty → IndexError → falls to except → 1% fallback<br>• Tick size assumed = 1.0 (line 105 comment) — hardcoded, not dynamic |
| **Dependencies** | Action Server (localhost:8080), httpx.AsyncClient, json |
| **Failure Modes** | All errors silently fall back to 1% fixed SL. No logging of why SL was set to fallback. `json.loads(resp.json())` double-decode is the single highest-priority bug in this file. |

---

## Cross-Module Flow: Alpha Rotation Execution

```
IgnitionBridgeTask._execute_rotation()
    │
    ├── hub.get_price(ETH_SYM) → entry_price
    ├── LiquidityAwareStopLoss(entry_price, ...)
    │   ├── .initialize() → HTTP to Action Server → UDC walls → SL price
    │   └── .sl_price used in alert message
    │
    └── ExecutionEngine.predatory_execute(ETH_SYM, "buy", $50K)
        ├── estimate_slippage() → new DataEngine → OB walk
        ├── slip > 0.15% → TWAP (5 fragments, 0.5s spacing)
        └── slip ≤ 0.15% → Market (STUBBED — no actual order)
```

---

## Failure Modes Summary

| # | Failure | Severity | Trigger |
|:--|:--|:--|:--|
| FE-01 | Stub execution — no real orders | CRITICAL | IgnitionBridge calls predatory_execute — prints but no trade placed |
| FE-02 | DataEngine bypasses Hub cache | HIGH | estimate_slippage creates new DataEngine — no TTL, redundant connections |
| FE-03 | json.loads(resp.json()) double-decode | HIGH | Action Server returns dict → TypeError → 1% fallback SL |
| FE-04 | DynamicTrailingStop single-direction | MEDIUM | No SHORT trailing — bearish moves unprotected |
| FE-05 | Tick size hardcoded to 1.0 | LOW | Incorrect for high-precision assets (SOL, HYPE, TAO) |
| FE-06 | accumulated_qty == 0 → ZeroDivisionError | MEDIUM | Empty OB or all levels at price=0 |
