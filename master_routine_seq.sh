#!/bin/bash
# master_routine.sh — High-Conviction Institutional Audit Routine
# ═════════════════════════════════════════════════════════════════

BTC_SYM="BTC/USDT:USDT"
ETH_SYM="ETH/USDT:USDT"
ASSETS="BTC,ETH"
ALPHA_ASSETS="BTC,ETH,SOL,HYPE"
BASE_URL="http://localhost:8080/api/actions/funding-action-server"
TOKEN="RAHbfBII5ONWhNI5j-wnZvy6paYyyzl4cLwcnl6BKqs"

echo "🚀 Starting Master Routine..."

# ── 🔬 FLOW-SCALP ─────────────────────────────────────────────────────
echo "Running FLOW-SCALP (Toxicity  Microstructure)..."
curl -s -X POST "$BASE_URL/get-toxicity-index/run" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"symbol\": \"$BTC_SYM\", \"ob_depth\": 20, \"trade_limit\": 500}" > scalp_tox_btc.json 
curl -s -X POST "$BASE_URL/get-toxicity-index/run" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"symbol\": \"$ETH_SYM\", \"ob_depth\": 20, \"trade_limit\": 500}" > scalp_tox_eth.json 
curl -s -X POST "$BASE_URL/microstructure-audit/run" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"symbol\": \"$BTC_SYM\"}" > scalp_audit_btc.json 
curl -s -X POST "$BASE_URL/microstructure-audit/run" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"symbol\": \"$ETH_SYM\"}" > scalp_audit_eth.json 
curl -s -X POST "$BASE_URL/get-ob-walls/run" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"symbol\": \"$BTC_SYM\", \"depth\": 20}" > scalp_walls_btc.json 
curl -s -X POST "$BASE_URL/get-ob-walls/run" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"symbol\": \"$ETH_SYM\", \"depth\": 20}" > scalp_walls_eth.json 

# ── 📊 FLOW-INTRADAY ──────────────────────────────────────────────────
echo "Running FLOW-INTRADAY (Basis  Confluence)..."
curl -s -X POST "$BASE_URL/get-basis/run" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d '{"symbol_spot": "BTC/USDT", "symbol_perp": "BTC/USDT:USDT"}' > intraday_basis_btc.json 
curl -s -X POST "$BASE_URL/get-basis/run" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d '{"symbol_spot": "ETH/USDT", "symbol_perp": "ETH/USDT:USDT"}' > intraday_basis_eth.json 
curl -s -X POST "$BASE_URL/get-tactical-report/run" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"assets\": \"$ASSETS\", \"strategy\": \"scalp\"}" > intraday_tactical_scalp.json 
curl -s -X POST "$BASE_URL/get-tactical-report/run" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"assets\": \"$ASSETS\", \"strategy\": \"swing\"}" > intraday_tactical_swing.json 
curl -s -X POST "$BASE_URL/get-ultra-deep-confluence/run" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"assets\": \"$ASSETS\", \"depth\": 100}" > intraday_udc.json 

# ── 🛁 ETH ELE TRANSITION ─────────────────────────────────────────────
echo "Running ELE TRANSITION (ETH Specialized)..."
curl -s -X POST "$BASE_URL/eth-ele-audit/run" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d '{"symbol": "ETH/USDT:USDT"}' > ele_potential.json 
curl -s -X POST "$BASE_URL/get-ob-walls/run" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"symbol\": \"$ETH_SYM\", \"depth\": 100}" > eth_walls_d100.json 

# ── 🔥 ALPHA IGNITION ─────────────────────────────────────────────────
echo "Running ALPHA IGNITION (Global Snapshot)..."
curl -s -X POST "$BASE_URL/get-full-market-snapshot/run" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"assets\": \"$ALPHA_ASSETS\"}" > alpha_snapshot.json 
curl -s -X POST "$BASE_URL/microstructure-audit/run" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"symbol\": \"BTC/USDT:USDT\"}" > btc_ignition_audit.json 
curl -s -X POST "$BASE_URL/microstructure-audit/run" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "{\"symbol\": \"ETH/USDT:USDT\"}" > eth_ignition_audit.json 

# ── 🏆 HTF ELITE Z-SCORE ──────────────────────────────────────────────
echo "Running HTF ELITE Z-SCORE (Multi-TF Audit)..."
python3 strategies/zscore_chart.py BTC > /dev/null 2>1 
python3 strategies/zscore_chart.py ETH > /dev/null 2>1 

wait
echo "✅ All Routines Complete. Interpreting data..."
