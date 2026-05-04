Ran command: `# Detect ICT/SFP Confluence Triggers (PDH, PDL, H4, etc.)
curl -s -X POST http://localhost:8080/api/actions/funding-action-server/detect-confluence-trigger/run -H "Content-Type: application/json" -d '{"assets": "BTC,ETH"}' > ict_triggers.json

# Detailed Audit for ETH (ELE Transition) and BTC
curl -s -X POST http://localhost:8080/api/actions/funding-action-server/eth-ele-audit/run -H "Content-Type: application/json" -d '{"symbol": "ETH/USDT:USDT"}' > eth_ict_audit.json &
curl -s -X POST http://localhost:8080/api/actions/funding-action-server/microstructure-audit/run -H "Content-Type: application/json" -d '{"symbol": "BTC/USDT:USDT"}' > btc_ict_audit.json &

# Get Next Liquidity Pools (D100)
curl -s -X POST http://localhost:8080/api/actions/funding-action-server/get-ultra-deep-confluence/run -H "Content-Type: application/json" -d '{"assets": "BTC,ETH", "depth": 100}' > ict_liquidity_pools.json &

wait
echo "ICT Setup Scan complete"`
Ran command: `cat ict_triggers.json btc_ict_audit.json eth_ict_audit.json ict_liquidity_pools.json intraday_basis_btc.json intraday_basis_eth.json`

# 🏹 Intraday Institutional Setup: ICT Ignition & Flow-Trend

While we are not currently testing a major PDH/PDL sweep (SFP), the microstructure has shifted into a **High-Conviction Ignition Phase**. This is the institutional move following the accumulation we identified earlier.

---

## 🟠 BTC/USDT: Intraday "Spot Lead" Long

**Institutional Context**: Spot Premium (`-0.06%`) remains the anchor. Institutions are paying more for the underlying asset than the perp, which is a structural floor.

### 🎯 Setup: The Order Book Ignition
- **Current Price**: ~$77,009
- **Confirmation**: `obi_20` is at a massive **0.98** (Maxed out buy pressure) with positive CVD (`+290k USD`).
- **Entry Logic**: High-volume breakout participation. The current consolidation is institutional absorption of the $77,000 wall.

### 🚀 Targets (Liquidity Pools)
1.  **Target 1 (Session High)**: **$77,150**. (Previous H1 High / Liquidity Pool).
2.  **Target 2 (HTF Liquidity)**: **$77,400**. (Daily High / Major Ask Wall cluster).

### 🛑 Invalidation (The Kill-Zone)
- **Hard Stop**: **$76,880**. (Below the current Spot Premium floor and the D100 support cluster).
- **Time Invalidation**: If the price remains stagnant for >4 hours while `basis_pct` moves to positive (>0.01%), exit at market.

---

## 🔵 ETH/USDT: Intraday "ELE" Transition

**Institutional Context**: ETH is lagging BTC but showing similar Spot Premium (`-0.046%`).

### 🎯 Setup: The Laggard Catch-up
- **Current Price**: ~$2324
- **Confirmation**: Wait for BTC to clear $77,015. ETH usually follows BTC with a 2-5 minute delay in these microstructure regimes.
- **Entry Logic**: Participation in the "Safe Haven Rotation" identified in the master matrix.

### 🚀 Targets (Liquidity Pools)
1.  **Target 1**: **$2335**. (H4 High / Major Ask concentration).
2.  **Target 2**: **$2352**. (Weekly High / Significant Liquidity Pool).

### 🛑 Invalidation
- **Hard Stop**: **$2315**. (Below the recent consolidation low and the $2320 spot wall).

---

## 🧠 ICT Senior Interpretation

| Concept | Application | Context |
| :--- | :--- | :--- |
| **Liquidity Sweep** | **NONE CURRENTLY** | We are in the *Expansion Phase* after the sweep. Entering now is "Trading the Expansion". |
| **Order Block (OB)** | **$76,950 - $77,000** | This is the current Institutional Buy Zone (confirmed by OBI 0.98). |
| **Fair Value Gap (FVG)** | **$77,050+** | Expect a rapid move through the liquidity void once the $77,010 wall is cleared. |

> [!IMPORTANT]
> **Intraday Verdict**: We are in a **Trend-Following Regime** powered by Spot Accumulation. The "Setup" is to ride the expansion towards the Daily Highs ($77,400 / $2350). The lack of an immediate sweep trigger means the "Smart Money" is already positioned and is now pushing the price.

**Risk-Flip Reminder**: Keep an eye on `basis_pct`. As long as it's negative, the trend is your friend. If it flips positive, retail FOMO has arrived, and it's time to take profits.
