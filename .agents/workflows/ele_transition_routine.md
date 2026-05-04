---
description: ETH Liquidity Engine (SFP to Intraday Transition) Routine
---

// turbo-all
# ETH ELE Transition Routine

High-probability protocol for capturing ETH SFPs and transitioning them into intraday trend positions based on the 'ETH Liquidity Engine' (ELE) logic.

## 1. Audit Current ELE Potential
Check if SFP levels are being hit and if microstructure supports a transition.

```bash
# Execute specialized ELE Audit
curl -X POST http://localhost:8080/api/actions/funding-action-server/eth-ele-audit/run -H "Content-Type: application/json" -d '{"symbol": "ETH/USDT:USDT"}' > ele_potential.json
```

## 2. Microstructure Secondary Validation
If `transition_potential` is "MEDIUM" or "HIGH", validate with deep OBI and Basis.

```bash
# Fetch deep OB and Spot/Perp Basis
curl -X POST http://localhost:8080/api/actions/funding-action-server/get-ob-walls/run -H "Content-Type: application/json" -d '{"symbol": "ETH/USDT:USDT", "depth": 100}' > eth_walls.json
curl -X POST http://localhost:8080/api/actions/funding-action-server/get-basis/run -H "Content-Type: application/json" -d '{"symbol_spot": "ETH/USDT", "symbol_perp": "ETH/USDT:USDT"}' > eth_basis.json
```

## 3. Decision Matrix
- **Go (Intraday)**: `verdict` == "ELE_ACTIVE" AND `basis_pct` > 0.05% (for longs) AND `obi` > 0.4.
- **Go (Scalp Only)**: `transition_potential` == "MEDIUM" AND `obi` > 0.2.
- **No Trade**: `verdict` == "NO_EDGE".
