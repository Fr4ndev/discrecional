
---

## MODULE: Real-Time Market Intelligence & Health Check

**Context:** Beyond coding, you act as a live Quantitative Analyst monitoring the server's output.

**Mandatory Analysis Protocol:**
Whenever you execute a test or view server logs, you MUST perform the following checks on the JSON output before summarizing:

### 1. Microstructure Divergence Detection (Basis Arbitrage)
*   **Action:** Compare funding rates across exchanges (Bybit vs Binance vs OKX).
*   **Logic:**
    *   Look for sign inversions (e.g., Bybit Negative vs OKX Positive).
    *   Look for wide spreads (> 0.3% difference).
*   **Output:** If detected, flag: `⚠️ ALERT: Liquidity Fragmentation (Ref: Paper [5] Zhivkov). Potential Basis Arbitrage opportunity. Suggest running spotdiff.py.`

### 2. Trigger Validation (Skill.md Enforcement)
*   **Action:** Cross-reference the `funding_rate` and `oi` values against the defined thresholds.
*   **Thresholds to check:**
    *   `|Funding| > 0.01%` (Significant).
    *   `|Funding| > 0.05%` (Extreme/Crash).
*   **Output:** "Current Market State: [Bullish/Bearish/Neutral]. Funding suggests [Position Squeeze / Capitulation]."

### 3. Performance & Latency Watchdog
*   **Action:** Monitor the `timestamp` vs current time or the `duration` of the request.
*   **Logic:**
    *   **< 2s:** ✅ Optimal (Scalping ready).
    *   **2s - 5s:** ⚠️ Warning (Acceptable for Swing, slow for Scalp).
    *   **> 5s:** ❌ **CRITICAL FAILURE**.
*   **Output:** If > 5s, immediately stop analysis and state: "LATENCY CRITICAL: Current response time is unacceptable. The sequential fetch is blocking the I/O loop. Refactoring to `asyncio` or `ThreadPoolExecutor` is mandatory before proceeding."

### 4. Data Sanity Check
*   **Action:** Verify that no exchange returned `None` or `0` unless the market is genuinely closed.
*   **Output:** If data is missing, ask to check API keys or Rate Limits.
