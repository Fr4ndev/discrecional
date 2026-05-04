#!/bin/bash
# scripts/ignite_omega.sh — The "Brutal" Comprehensive Routine
# ═════════════════════════════════════════════════════════════════
# Combines Macro HTF, Microstructure, ICT Sweeps, and Institutional Flows.

BTC_SYM="BTC/USDT:USDT"
ETH_SYM="ETH/USDT:USDT"
ASSETS="BTC,ETH"
BASE_URL="http://localhost:8080/api/actions/funding-action-server"
# Authentication removed for local mode

echo "🌌 [OMEGA] Starting Brutal Integrated Routine..."

# 1. Macro HTF Audit (Elite Z-Score)
echo "🎯 [HTF] Running Elite Z-Score Audit..."
python3 strategies/zscore_chart.py BTC > /dev/null 2>&1 &
python3 strategies/zscore_chart.py ETH > /dev/null 2>&1 &

# 2. Microstructure & Toxicity (Micro-Liquidity)
echo "🔬 [MICRO] Running Toxicity & Microstructure Audit..."
curl -s -X POST "$BASE_URL/get-toxicity-index/run" -H "Content-Type: application/json"  -d "{\"symbol\": \"$BTC_SYM\", \"ob_depth\": 20, \"trade_limit\": 500}" > data/pulse_tox_btc.json &
curl -s -X POST "$BASE_URL/get-toxicity-index/run" -H "Content-Type: application/json"  -d "{\"symbol\": \"$ETH_SYM\", \"ob_depth\": 20, \"trade_limit\": 500}" > data/pulse_tox_eth.json &

# 3. Ultra Deep Confluence (UDC Floor)
echo "🛡️ [UDC] Running Ultra Deep Confluence Audit..."
curl -s -X POST "$BASE_URL/get-ultra-deep-confluence/run" -H "Content-Type: application/json"  -d "{\"assets\": \"$ASSETS\", \"depth\": 100}" > data/final_udc.json &

# 4. (DEPRECATED) Guardian Sentinel Health Check
echo "📡 [PHD] Guardian check skipped (Decoupled Flow)..."
# Logic removed to avoid macro noise from Guardian.

# 5. ICT V16 Standalone Scan (Optional, since it's in Guardian, but good for instant report)
# echo "🚨 [ICT] Forcing Instant ICT Scan..."
# (Logic would go here if we wanted a separate CLI report)

wait
echo "✅ [OMEGA] Brutal Routine Complete. Systems at 100% capacity."
echo "📈 Data persisted in /data/ directory."
