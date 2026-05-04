#!/usr/bin/env python3
"""
⚠️ DEPRECATED — PhD Cohesion Loop Cycle 5
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This script is now redundant. Its core logic has been centralized in:
- core/Core_Intelligence_Hub.py (Microstructure analysis)
- utils/helpers.py (calculate_institutional_score)
- funding_action_server/actions/market_actions.py (get_system_health)

Maintain for backward compatibility only. Do NOT add new logic here.
"""
import json
import os

def load_json(filename):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

assets = ["btc", "eth"]

print("==== 🔬 FLOW-SCALP ====")
for asset in assets:
    tox = load_json(f"scalp_tox_{asset}.json")
    audit = load_json(f"scalp_audit_{asset}.json")
    
    print(f"[{asset.upper()}]")
    try:
        toxicity_idx = tox.get("toxicity", {}).get("index", 0)
        abs_verdict = tox.get("absorption", {}).get("verdict", "N/A")
        iceberg_score = tox.get("iceberg", {}).get("score", 0)
    except AttributeError:
        toxicity_idx, abs_verdict, iceberg_score = 0, "N/A", 0
        
    try:
        micro = audit.get("microstructure", {})
        obi_20 = micro.get("obi_20", audit.get("obi_20", 0))
        cvd = micro.get("cvd_100_trades_usd", audit.get("cvd_100_trades_usd", 0))
        basis = micro.get("basis_pct", audit.get("basis_pct", 0))
        zscore = micro.get("zscore_m5", audit.get("zscore_m5", 0))
    except AttributeError:
        obi_20, cvd, basis, zscore = 0, 0, 0, 0
    
    print(f"  Toxicity Index: {toxicity_idx}")
    print(f"  Absorption: {abs_verdict}")
    print(f"  Iceberg Score: {iceberg_score}")
    print(f"  OBI_20: {obi_20}")
    print(f"  CVD 100 Trades: {cvd}")
    print(f"  Basis PCT: {basis}")
    print(f"  Z-Score M5: {zscore}")

    score = 0
    if toxicity_idx > 0.60: score += 3
    if abs(obi_20) > 0.35: score += 3
    if iceberg_score > 0.40: score += 2
    if (cvd > 0 and obi_20 > 0) or (cvd < 0 and obi_20 < 0): score += 2
    if obi_20 > 0 and basis < 0: score += 1
    elif obi_20 < 0 and basis > 0: score += 1
    
    print(f"  -> Scalp Score: {score}")

print("\n==== 📊 FLOW-INTRADAY ====")
for asset in assets:
    basis_data = load_json(f"intraday_basis_{asset}.json")
    print(f"[{asset.upper()}] Basis PCT: {basis_data.get('basis_pct', 'N/A')}")

udc = load_json("intraday_udc.json")
print("UDC Data:", json.dumps(udc, indent=2)[:500])

tactical_scalp = load_json("intraday_tactical_scalp.json")
print("Tactical Scalp:", json.dumps(tactical_scalp, indent=2)[:500])

tactical_swing = load_json("intraday_tactical_swing.json")
print("Tactical Swing:", json.dumps(tactical_swing, indent=2)[:500])

print("\n==== 🛁 ETH ELE TRANSITION ====")
ele = load_json("ele_potential.json")
print("ELE Potential:", json.dumps(ele, indent=2)[:500])

print("\n==== 🔥 ALPHA IGNITION ====")
alpha = load_json("alpha_snapshot.json")
print("Alpha Snapshot:", json.dumps(alpha, indent=2)[:500])

