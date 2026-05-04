---
description: Alpha Ignition & Momentum Cluster Routine
---

// turbo-all
# Alpha Ignition Routine

Identifies volume velocity bursts and validates if they are institutional "Ignition" moves or retail exhaustion.

## 1. Detect Volume Anomalies
Run the market snapshot to check for OI and OBI spikes across the universe.

```bash
# Fetch global snapshot
curl -X POST http://localhost:8080/api/actions/funding-action-server/get-full-market-snapshot/run -H "Content-Type: application/json" -d '{"assets": "BTC,ETH,SOL,HYPE"}' > alpha_snapshot.json
```

## 2. Validate Ignition Cluster
For any asset with `trigger_level` == "SENSITIVE", perform a PhD Micro-Audit.

```bash
# Targeted PhD Audit (Example for BTC)
curl -X POST http://localhost:8080/api/actions/funding-action-server/microstructure-audit/run -H "Content-Type: application/json" -d '{"symbol": "BTC/USDT:USDT"}' > btc_ignition_audit.json
```

## 3. Absorption Check
Compare `cvd_100_trades_usd` against `obi_20`. 
- **Institutional Ignition**: Price moving UP + CVD positive + OBI > 0.3.
- **Absorption Trap**: Price moving UP + CVD positive + OBI < -0.3 (Walls absorbing the move).
- **Retail FOMO**: Price moving UP + OBI > 0.5 + Basis is Positive (Perp premium).
