#!/bin/bash
cd "$(dirname "$0")/../.."
# run_flows.sh — Modular Execution Script for Senior Desk Flows (PhD Edition)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BASE_URL="http://localhost:8080/api/actions/funding-action-server"
BTC_SYM="BTC/USDT:USDT"
ETH_SYM="ETH/USDT:USDT"
ASSETS="BTC,ETH"
# Authentication removed for local execution

SNAPSHOT_DIR="data/snapshots"
mkdir -p "$SNAPSHOT_DIR"

case "$1" in
    "turbo")
        echo "🚀 Running /turbo-all (PhD Level Acquisition)..."
        # Snapshot & Z-Score
        curl -s -X POST "$BASE_URL/get-full-market-snapshot/run" -H "Content-Type: application/json"  -d "{\"assets\": \"$ASSETS\"}" > "$SNAPSHOT_DIR/turbo_snapshot.json" &
        curl -s -X POST "$BASE_URL/get-zscore-vs-history/run" -H "Content-Type: application/json"  -d "{\"assets\": \"$ASSETS\"}" > "$SNAPSHOT_DIR/turbo_zscore.json" &
        
        # Deep Microstructure for BTC
        curl -s -X POST "$BASE_URL/get-toxicity-index/run" -H "Content-Type: application/json"  -d "{\"symbol\": \"$BTC_SYM\", \"ob_depth\": 20, \"trade_limit\": 500}" > "$SNAPSHOT_DIR/turbo_tox_btc.json" &
        curl -s -X POST "$BASE_URL/get-ob-walls/run" -H "Content-Type: application/json"  -d "{\"symbol\": \"$BTC_SYM\", \"depth\": 50}" > "$SNAPSHOT_DIR/turbo_walls_btc.json" &
        
        wait
        echo "✅ Check: turbo_snapshot.json | turbo_tox_btc.json | turbo_walls_btc.json"
        ;;
    "sfp")
        echo "🏹 Running /sfp-confluence (Institutional Reversal)..."
        curl -s -X POST "$BASE_URL/detect-confluence-trigger/run" -H "Content-Type: application/json"  -d "{\"assets\": \"$ASSETS\"}" > "$SNAPSHOT_DIR/sfp_triggers.json"
        # Deep Depth for the leader
        curl -s -X POST "$BASE_URL/get-ultra-deep-confluence/run" -H "Content-Type: application/json"  -d "{\"assets\": \"BTC\", \"depth\": 100}" > "$SNAPSHOT_DIR/sfp_depth_btc.json" &
        curl -s -X POST "$BASE_URL/get-toxicity-index/run" -H "Content-Type: application/json"  -d "{\"symbol\": \"$BTC_SYM\", \"ob_depth\": 20}" > "$SNAPSHOT_DIR/sfp_tox_btc.json" &
        wait
        echo "✅ Check: sfp_triggers.json | sfp_tox_btc.json"
        ;;
    "scalp")
        echo "🧩 Running /flow-scalp (Micro-Trend Explosion)..."
        curl -s -X POST "$BASE_URL/get-toxicity-index/run" -H "Content-Type: application/json"  -d "{\"symbol\": \"$BTC_SYM\", \"ob_depth\": 20}" > "$SNAPSHOT_DIR/scalp_tox_btc.json"
        curl -s -X POST "$BASE_URL/get-ob-walls/run" -H "Content-Type: application/json"  -d "{\"symbol\": \"$BTC_SYM\", \"depth\": 20}" > "$SNAPSHOT_DIR/scalp_walls_btc.json"
        ;;
    "intraday")
        echo "🎯 Running /flow-intraday (Session Capture)..."
        curl -s -X POST "$BASE_URL/get-full-market-snapshot/run" -H "Content-Type: application/json"  -d "{\"assets\": \"$ASSETS\"}" > "$SNAPSHOT_DIR/intraday_snapshot.json"
        curl -s -X POST "$BASE_URL/get-ultra-deep-confluence/run" -H "Content-Type: application/json"  -d "{\"assets\": \"BTC\", \"depth\": 100}" > "$SNAPSHOT_DIR/intraday_udc.json"
        ;;
    "swing")
        echo "📅 Running /flow-swing (Regime Change)..."
        curl -s -X POST "$BASE_URL/get-zscore-vs-history/run" -H "Content-Type: application/json"  -d "{\"assets\": \"$ASSETS\"}" > "$SNAPSHOT_DIR/swing_zscore.json"
        ;;
    "alpha")
        echo "🛰️ Running /flow-alpha-sentinel (The Hybrid Master)..."
        # Combinación de todo
        ./scripts/ops/run_flows.sh turbo
        ./scripts/ops/run_flows.sh intraday
        ;;
    "ignition")
        echo "🔥 Running /alpha-ignition (Momentum Audit)..."
        curl -s -X POST "$BASE_URL/get-full-market-snapshot/run" -H "Content-Type: application/json"  -d '{"assets": "BTC,ETH,SOL,HYPE"}' > "$SNAPSHOT_DIR/alpha_snapshot.json"
        ;;
    "decision_matrix")
        echo "🧬 Running /decision-matrix (Confluence Audit)..."
        # Macro + Micro + UDC
        python3 strategies/zscore_chart.py BTC > /dev/null 2>&1
        # Move zscore to data/ if it was saved in root
        [ -f zscore_elite_btc.json ] && mv zscore_elite_btc.json data/
        
        curl -s -X POST "$BASE_URL/get-toxicity-index/run" -H "Content-Type: application/json"  -d "{\"symbol\": \"$BTC_SYM\", \"ob_depth\": 20}" > data/pulse_tox_btc.json
        curl -s -X POST "$BASE_URL/get-ultra-deep-confluence/run" -H "Content-Type: application/json"  -d "{\"assets\": \"$ASSETS\", \"depth\": 100}" > data/final_udc.json
        ;;
    *)
        echo "Usage: ./run_flows.sh {turbo|sfp|scalp|intraday|swing|alpha}"
        exit 1
        ;;
esac
