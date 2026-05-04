#!/bin/bash
cd "$(dirname "$0")/../.."
# run_scalp_workflow.sh — High-Frequency Micro-Trend Flow
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Variables
BTC_SYM="BTC/USDT:USDT"
ETH_SYM="ETH/USDT:USDT"
BASE_URL="http://localhost:8080/api/actions/funding-action-server"

# Variables de Salida
SNAPSHOT_DIR="data/snapshots"
mkdir -p "$SNAPSHOT_DIR"

echo "🚀 Running FLOW-SCALP..."

# ── PASO 1: Toxicity Index (VPIN — Stress del Market Maker) ───────────
echo "Step 1: Toxicity Index..."
curl -s -X POST "$BASE_URL/get-toxicity-index/run" \
  -H "Content-Type: application/json" \
   \
  -d "{\"symbol\": \"$BTC_SYM\", \"ob_depth\": 20, \"trade_limit\": 500}" \
  > "$SNAPSHOT_DIR/scalp_tox_btc.json" &

curl -s -X POST "$BASE_URL/get-toxicity-index/run" \
  -H "Content-Type: application/json" \
   \
  -d "{\"symbol\": \"$ETH_SYM\", \"ob_depth\": 20, \"trade_limit\": 500}" \
  > "$SNAPSHOT_DIR/scalp_tox_eth.json" &

wait

# ── PASO 2: Microstructure Audit (confirmación direccional) ─────────────
echo "Step 2: Microstructure Audit..."
curl -s -X POST "$BASE_URL/microstructure-audit/run" \
  -H "Content-Type: application/json" \
   \
  -d "{\"symbol\": \"$BTC_SYM\"}" \
  > "$SNAPSHOT_DIR/scalp_audit_btc.json" &

curl -s -X POST "$BASE_URL/microstructure-audit/run" \
  -H "Content-Type: application/json" \
   \
  -d "{\"symbol\": \"$ETH_SYM\"}" \
  > "$SNAPSHOT_DIR/scalp_audit_eth.json" &

wait

# ── PASO 3: OB Walls D20 (mapa de landmines) ───────────────────────────
echo "Step 3: OB Walls D20..."
curl -s -X POST "$BASE_URL/get-ob-walls/run" \
  -H "Content-Type: application/json" \
   \
  -d "{\"symbol\": \"$BTC_SYM\", \"depth\": 20}" \
  > "$SNAPSHOT_DIR/scalp_walls_btc.json" &

curl -s -X POST "$BASE_URL/get-ob-walls/run" \
  -H "Content-Type: application/json" \
   \
  -d "{\"symbol\": \"$ETH_SYM\", \"depth\": 20}" \
  > "$SNAPSHOT_DIR/scalp_walls_eth.json" &

wait

echo "✅ FLOW-SCALP complete."
echo "── VPIN:  $SNAPSHOT_DIR/scalp_tox_*.json"
echo "── Audit: $SNAPSHOT_DIR/scalp_audit_*.json"
echo "── Walls: $SNAPSHOT_DIR/scalp_walls_*.json"
