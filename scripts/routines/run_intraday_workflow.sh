#!/bin/bash
cd "$(dirname "$0")/../.."
# run_intraday_workflow.sh — Daily Session Capture Flow
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Variables
ASSETS="BTC,ETH"
BTC_SYM="BTC/USDT:USDT"
ETH_SYM="ETH/USDT:USDT"
BASE_URL="http://localhost:8080/api/actions/funding-action-server"

# Variables de Salida
SNAPSHOT_DIR="data/snapshots"
mkdir -p "$SNAPSHOT_DIR"

echo "🚀 Running FLOW-INTRADAY..."

# ── PASO 1: Basis — Floor/Ceiling de la sesión ─────────────────────────
echo "Step 1: Basis..."
curl -s -X POST "$BASE_URL/get-basis/run" \
  -H "Content-Type: application/json" \
   \
  -d '{"symbol_spot": "BTC/USDT", "symbol_perp": "BTC/USDT:USDT"}' \
  > "$SNAPSHOT_DIR/intraday_basis_btc.json" &

curl -s -X POST "$BASE_URL/get-basis/run" \
  -H "Content-Type: application/json" \
   \
  -d '{"symbol_spot": "ETH/USDT", "symbol_perp": "ETH/USDT:USDT"}' \
  > "$SNAPSHOT_DIR/intraday_basis_eth.json" &

wait

# ── PASO 2: Tactical Report (dual mode) ────────────────────────────────
echo "Step 2: Tactical Report..."
curl -s -X POST "$BASE_URL/get-tactical-report/run" \
  -H "Content-Type: application/json" \
   \
  -d "{\"assets\": \"$ASSETS\", \"strategy\": \"scalp\"}" \
  > "$SNAPSHOT_DIR/intraday_tactical_scalp.json" &

curl -s -X POST "$BASE_URL/get-tactical-report/run" \
  -H "Content-Type: application/json" \
   \
  -d "{\"assets\": \"$ASSETS\", \"strategy\": \"swing\"}" \
  > "$SNAPSHOT_DIR/intraday_tactical_swing.json" &

wait

# ── PASO 3: Ultra-Deep Confluence D100 (mapa institucional) ────────────
echo "Step 3: Ultra-Deep Confluence..."
curl -s -X POST "$BASE_URL/get-ultra-deep-confluence/run" \
  -H "Content-Type: application/json" \
   \
  -d "{\"assets\": \"$ASSETS\", \"depth\": 100}" \
  > "$SNAPSHOT_DIR/intraday_udc.json"

echo "✅ FLOW-INTRADAY complete."
echo "── Floor/Ceiling: $SNAPSHOT_DIR/intraday_basis_*.json"
echo "── Confluencia:   $SNAPSHOT_DIR/intraday_udc.json"
echo "── Táctico:       $SNAPSHOT_DIR/intraday_tactical_scalp.json + $SNAPSHOT_DIR/intraday_tactical_swing.json"
