#!/bin/bash
cd "$(dirname "$0")/../.."
# run_sfp_routine.sh — Institutional Reversal Flow
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BASE_URL="http://localhost:8080/api/actions/funding-action-server"
ASSETS="BTC,ETH"
AUTH_H=""

# Variables de Salida
SNAPSHOT_DIR="data/snapshots"
mkdir -p "$SNAPSHOT_DIR"

echo "🚀 Running SFP-CONFLUENCE-ROUTINE..."

# Step 1: Detecting Confluence Trigger
echo "Step 1: Detecting Confluence Trigger..."
curl -s -X POST "$BASE_URL/detect-confluence-trigger/run" \
  -H "Content-Type: application/json" \
  -H "$AUTH_H" \
  -d "{\"assets\": \"$ASSETS\"}" \
  > "$SNAPSHOT_DIR/sfp_triggers.json"

# Step 2: Ultra-Deep Depth Check (for BTC and ETH)
echo "Step 2: Ultra-Deep Depth Audit..."
curl -s -X POST "$BASE_URL/get-ultra-deep-confluence/run" \
  -H "Content-Type: application/json" \
  -H "$AUTH_H" \
  -d "{\"assets\": \"BTC\", \"depth\": 100}" \
  > "$SNAPSHOT_DIR/sfp_depth_btc.json" &

curl -s -X POST "$BASE_URL/get-ultra-deep-confluence/run" \
  -H "Content-Type: application/json" \
  -H "$AUTH_H" \
  -d "{\"assets\": \"ETH\", \"depth\": 100}" \
  > "$SNAPSHOT_DIR/sfp_depth_eth.json" &

wait

echo "✅ SFP-CONFLUENCE-ROUTINE complete. Check: $SNAPSHOT_DIR/sfp_triggers.json | $SNAPSHOT_DIR/sfp_depth_*.json"
