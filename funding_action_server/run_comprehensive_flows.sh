#!/bin/bash
# run_comprehensive_flows.sh

ASSETS="BTC,ETH"
BTC_SYM="BTC/USDT:USDT"
ETH_SYM="ETH/USDT:USDT"
BASE_URL="http://localhost:8080/api/actions/funding-action-server"
OUT_DIR="comprehensive_results"

mkdir -p "$OUT_DIR"

echo "🚀 Starting COMPREHENSIVE FLOW EXECUTION..."

# ── 1. FLOW-SCALP ─────────────────────────────────────────────────────
echo "Running FLOW-SCALP..."
curl -s -X POST "$BASE_URL/get-toxicity-index/run" -H "Content-Type: application/json" -d "{\"symbol\": \"$BTC_SYM\", \"ob_depth\": 20, \"trade_limit\": 500}" > "$OUT_DIR/scalp_tox_btc.json" &
curl -s -X POST "$BASE_URL/get-toxicity-index/run" -H "Content-Type: application/json" -d "{\"symbol\": \"$ETH_SYM\", \"ob_depth\": 20, \"trade_limit\": 500}" > "$OUT_DIR/scalp_tox_eth.json" &
curl -s -X POST "$BASE_URL/microstructure-audit/run" -H "Content-Type: application/json" -d "{\"symbol\": \"$BTC_SYM\"}" > "$OUT_DIR/scalp_audit_btc.json" &
curl -s -X POST "$BASE_URL/microstructure-audit/run" -H "Content-Type: application/json" -d "{\"symbol\": \"$ETH_SYM\"}" > "$OUT_DIR/scalp_audit_eth.json" &
curl -s -X POST "$BASE_URL/get-ob-walls/run" -H "Content-Type: application/json" -d "{\"symbol\": \"$BTC_SYM\", \"depth\": 20}" > "$OUT_DIR/scalp_walls_btc.json" &
curl -s -X POST "$BASE_URL/get-ob-walls/run" -H "Content-Type: application/json" -d "{\"symbol\": \"$ETH_SYM\", \"depth\": 20}" > "$OUT_DIR/scalp_walls_eth.json" &

# ── 2. FLOW-INTRADAY ──────────────────────────────────────────────────
echo "Running FLOW-INTRADAY..."
curl -s -X POST "$BASE_URL/get-basis/run" -H "Content-Type: application/json" -d '{"symbol_spot": "BTC/USDT", "symbol_perp": "BTC/USDT:USDT"}' > "$OUT_DIR/intraday_basis_btc.json" &
curl -s -X POST "$BASE_URL/get-basis/run" -H "Content-Type: application/json" -d '{"symbol_spot": "ETH/USDT", "symbol_perp": "ETH/USDT:USDT"}' > "$OUT_DIR/intraday_basis_eth.json" &
curl -s -X POST "$BASE_URL/get-tactical-report/run" -H "Content-Type: application/json" -d "{\"assets\": \"$ASSETS\", \"strategy\": \"scalp\"}" > "$OUT_DIR/intraday_tactical_scalp.json" &
curl -s -X POST "$BASE_URL/get-tactical-report/run" -H "Content-Type: application/json" -d "{\"assets\": \"$ASSETS\", \"strategy\": \"swing\"}" > "$OUT_DIR/intraday_tactical_swing.json" &
curl -s -X POST "$BASE_URL/get-ultra-deep-confluence/run" -H "Content-Type: application/json" -d "{\"assets\": \"$ASSETS\", \"depth\": 100}" > "$OUT_DIR/intraday_udc.json" &

# ── 3. ELE-TRANSITION (ETH specialized) ───────────────────────────────
echo "Running ELE-TRANSITION..."
curl -s -X POST "$BASE_URL/eth-ele-audit/run" -H "Content-Type: application/json" -d '{"symbol": "ETH/USDT:USDT"}' > "$OUT_DIR/ele_potential.json" &
curl -s -X POST "$BASE_URL/get-ob-walls/run" -H "Content-Type: application/json" -d '{"symbol": "ETH/USDT:USDT", "depth": 100}' > "$OUT_DIR/eth_walls_d100.json" &

# ── 4. ALPHA-IGNITION ─────────────────────────────────────────────────
echo "Running ALPHA-IGNITION..."
curl -s -X POST "$BASE_URL/get-full-market-snapshot/run" -H "Content-Type: application/json" -d '{"assets": "BTC,ETH,SOL,HYPE"}' > "$OUT_DIR/alpha_snapshot.json" &

# ── 5. ULTRA-DEEP ─────────────────────────────────────────────────────
echo "Running ULTRA-DEEP..."
# This is largely redundant with the above, but running specifically as defined
curl -s -X POST "$BASE_URL/get-ultra-deep-confluence/run" -H "Content-Type: application/json" -d "{\"assets\": \"$ASSETS\", \"depth\": 100}" > "$OUT_DIR/ud_confluence.json" &
curl -s -X POST "$BASE_URL/get-tactical-report/run" -H "Content-Type: application/json" -d "{\"assets\": \"$ASSETS\", \"strategy\": \"scalp\"}" > "$OUT_DIR/tactical_scalp.json" &
curl -s -X POST "$BASE_URL/get-tactical-report/run" -H "Content-Type: application/json" -d "{\"assets\": \"$ASSETS\", \"strategy\": \"swing\"}" > "$OUT_DIR/tactical_swing.json" &
curl -s -X POST "$BASE_URL/microstructure-audit/run" -H "Content-Type: application/json" -d "{\"symbol\": \"$BTC_SYM\"}" > "$OUT_DIR/audit_btc.json" &
curl -s -X POST "$BASE_URL/get-ob-walls/run" -H "Content-Type: application/json" -d "{\"symbol\": \"$BTC_SYM\", \"depth\": 100}" > "$OUT_DIR/walls_btc.json" &

echo "Waiting for all concurrent flows to complete..."
wait
echo "✅ ALL COMPREHENSIVE FLOWS COMPLETED."
