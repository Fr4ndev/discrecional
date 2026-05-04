#!/bin/bash
cd "$(dirname "$0")/../.."
# run_ele_routine.sh — Specialized ETH Transition Flow
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BASE_URL="http://localhost:8080/api/actions/funding-action-server"
ETH_SYM="ETH/USDT:USDT"
AUTH_H=""

# Variables de Salida
SNAPSHOT_DIR="data/snapshots"
mkdir -p "$SNAPSHOT_DIR"

echo "🚀 Running ELE-TRANSITION-ROUTINE..."

# Step 1: ELE Audit
echo "Step 1: ELE Audit..."
curl -s -X POST "$BASE_URL/eth-ele-audit/run" \
  -H "Content-Type: application/json" \
  -H "$AUTH_H" \
  -d "{\"symbol\": \"$ETH_SYM\"}" \
  > "$SNAPSHOT_DIR/ele_potential.json"

# Step 2: Microstructure Secondary Validation
echo "Step 2: Microstructure Validation (Walls + Basis)..."
curl -s -X POST "$BASE_URL/get-ob-walls/run" \
  -H "Content-Type: application/json" \
  -H "$AUTH_H" \
  -d "{\"symbol\": \"$ETH_SYM\", \"depth\": 100}" \
  > "$SNAPSHOT_DIR/eth_walls.json" &

curl -s -X POST "$BASE_URL/get-basis/run" \
  -H "Content-Type: application/json" \
  -H "$AUTH_H" \
  -d '{"symbol_spot": "ETH/USDT", "symbol_perp": "ETH/USDT:USDT"}' \
  > "$SNAPSHOT_DIR/eth_basis.json" &

wait

echo "✅ ELE-TRANSITION-ROUTINE complete. Check: $SNAPSHOT_DIR/ele_potential.json | $SNAPSHOT_DIR/eth_walls.json | $SNAPSHOT_DIR/eth_basis.json"
