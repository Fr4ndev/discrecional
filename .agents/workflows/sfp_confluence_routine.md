---
description: Advanced SFP & Level Confluence Routine
---

// turbo-all
# SFP Confluence Routine

Detects institutional reversals at daily/H4 highs and lows (Swing Failure Patterns).

## 1. Scan for Level Contest
Check all assets for proximity to SFP levels.

```bash
# Detect confluence triggers
curl -X POST http://localhost:8080/api/actions/funding-action-server/detect-confluence-trigger/run -H "Content-Type: application/json" -d '{"assets": "BTC,ETH,SOL"}' > sfp_triggers.json
```

## 2. Ultra-Deep Depth Check
For triggered assets, check the 100-level depth consensus to ensure institutional presence.

```bash
# 100-level depth audit
curl -X POST http://localhost:8080/api/actions/funding-action-server/get_ultra_deep_confluence/run -H "Content-Type: application/json" -d '{"assets": "BTC", "depth": 100}' > sfp_depth_btc.json
```

## 3. Final Execution Signal
- **SFP LONG**: Price breaches Daily Low AND `confluence_pct` > 70% AND `direction` == "LONG_BIAS".
- **SFP SHORT**: Price breaches Daily High AND `confluence_pct` > 70% AND `direction` == "SHORT_BIAS".
