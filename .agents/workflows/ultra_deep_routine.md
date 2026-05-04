---
description: Exhaustive Institutional Microstructure Audit for BTC/ETH
---

// turbo-all
# BTC/ETH Ultra-Deep Institutional Routine

This routine executes a high-probability audit of BTC/ETH microstructure across Scalp, Intraday, and Swing timeframes.

## 1. Execute Advanced Action Suite
Run this combined command to fire all institutional endpoints. Results are saved as JSON for synthesis.

```bash
# Variables
ASSETS="BTC,ETH"
BTC_SYM="BTC/USDT:USDT"
ETH_SYM="ETH/USDT:USDT"

# Execution Chain
curl -X POST http://localhost:8080/api/actions/funding-action-server/get-ultra-deep-confluence/run -H "Content-Type: application/json" -d "{\"assets\": \"$ASSETS\", \"depth\": 100}" > ud_confluence.json && \
curl -X POST http://localhost:8080/api/actions/funding-action-server/get-tactical-report/run -H "Content-Type: application/json" -d "{\"assets\": \"$ASSETS\", \"strategy\": \"scalp\"}" > tactical_scalp.json && \
curl -X POST http://localhost:8080/api/actions/funding-action-server/get-tactical-report/run -H "Content-Type: application/json" -d "{\"assets\": \"$ASSETS\", \"strategy\": \"swing\"}" > tactical_swing.json && \
curl -X POST http://localhost:8080/api/actions/funding-action-server/microstructure-audit/run -H "Content-Type: application/json" -d "{\"symbol\": \"$BTC_SYM\"}" > audit_btc.json && \
curl -X POST http://localhost:8080/api/actions/funding-action-server/get-ob-walls/run -H "Content-Type: application/json" -d "{\"symbol\": \"$BTC_SYM\", \"depth\": 100}" > walls_btc.json && \
curl -X POST http://localhost:8080/api/actions/funding-action-server/get-basis/run -H "Content-Type: application/json" -d "{\"symbol_spot\": \"BTC/USDT\", \"symbol_perp\": \"$BTC_SYM\"}" > basis_btc.json && \
curl -X POST http://localhost:8080/api/actions/funding-action-server/get-full-market-snapshot/run -H "Content-Type: application/json" -d "{\"assets\": \"$ASSETS\"}" > snapshot.json
```

## 2. Synthesis Protocol (Interpretation Guide)

| Metric | Bullish Confluence | Bearish Confluence |
| :--- | :--- | :--- |
| **Basis** | **Negative** (Spot Premium) | **Positive** (Perp / Retail FOMO) |
| **OBI (D20)** | **> 0.3** (Bid Pressure) | **< -0.3** (Ask Pressure) |
| **OI Δ** | **Expanding** (+5% or more) | **Contracting** (Liquidation) |
| **Walls** | **Clusters below price** | **Clusters above price** |

## 3. Decision Logic
1. **Long Setup**: Spot Premium + Bid Pressure (OBI > 0) + OI Accumulation.
2. **Short Setup**: Perp Premium + Ask Pressure (OBI < 0) + OI Exhaustion.
3. **Transition**: If Scalp OBI flips but Swing Basis remains Spot-Premium, hold for extension.
