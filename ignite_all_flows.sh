#!/bin/bash
# ignite_all_flows.sh — Senior Desk Total Ignition (Master Execution)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ── CONFIGURATION ──────────────────────────────────────────────
BASE_URL="http://localhost:8080/api/actions/funding-action-server"
# AUTH_H removed for LOCAL execution
OUT_DIR="data/ignition_results_$(date +%Y%m%d_%H%M%S)"
ASSETS="BTC,ETH"
ALPHA_ASSETS="BTC,ETH,SOL,HYPE"
BTC_SYM="BTC/USDT:USDT"
ETH_SYM="ETH/USDT:USDT"

mkdir -p "$OUT_DIR"

echo "🚀 IGNITING ALL SENIOR DESK FLOWS..."
echo "📂 Output directory: $OUT_DIR"

# ── 1. FLOW-SCALP (Toxicity & Microstructure) ───────────────────
echo "⚡ Running FLOW-SCALP..."
curl -s -X POST "$BASE_URL/get-toxicity-index/run" -H "Content-Type: application/json" -d "{\"symbol\": \"$BTC_SYM\", \"ob_depth\": 20, \"trade_limit\": 500}" > "$OUT_DIR/scalp_tox_btc.json" &
curl -s -X POST "$BASE_URL/get-toxicity-index/run" -H "Content-Type: application/json" -d "{\"symbol\": \"$ETH_SYM\", \"ob_depth\": 20, \"trade_limit\": 500}" > "$OUT_DIR/scalp_tox_eth.json" &
curl -s -X POST "$BASE_URL/microstructure-audit/run" -H "Content-Type: application/json" -d "{\"symbol\": \"$BTC_SYM\"}" > "$OUT_DIR/scalp_audit_btc.json" &
curl -s -X POST "$BASE_URL/microstructure-audit/run" -H "Content-Type: application/json" -d "{\"symbol\": \"$ETH_SYM\"}" > "$OUT_DIR/scalp_audit_eth.json" &

# ── 2. FLOW-INTRADAY (Basis & UDC) ─────────────────────────────
echo "📅 Running FLOW-INTRADAY..."
curl -s -X POST "$BASE_URL/get-basis/run" -H "Content-Type: application/json" -d '{"symbol_spot": "BTC/USDT", "symbol_perp": "BTC/USDT:USDT"}' > "$OUT_DIR/intraday_basis_btc.json" &
curl -s -X POST "$BASE_URL/get-basis/run" -H "Content-Type: application/json" -d '{"symbol_spot": "ETH/USDT", "symbol_perp": "ETH/USDT:USDT"}' > "$OUT_DIR/intraday_basis_eth.json" &
curl -s -X POST "$BASE_URL/get-ultra-deep-confluence/run" -H "Content-Type: application/json" -d "{\"assets\": \"$ASSETS\", \"depth\": 100}" > "$OUT_DIR/intraday_udc.json" &

# ── 3. FLOW-SWING (Regime & Snapshot) ──────────────────────────
echo "🏗️ Running FLOW-SWING..."
curl -s -X POST "$BASE_URL/get-full-market-snapshot/run" -H "Content-Type: application/json" -d "{\"assets\": \"$ASSETS\", \"ob_depth\": 50}" > "$OUT_DIR/swing_snapshot.json" &
curl -s -X POST "$BASE_URL/get-tactical-report/run" -H "Content-Type: application/json" -d "{\"assets\": \"$ASSETS\", \"strategy\": \"swing\"}" > "$OUT_DIR/swing_tactical.json" &

# ── 4. ALPHA & CONFLUENCE (SFP + Ignition) ────────────────────
echo "🔥 Running ALPHA & CONFLUENCE..."
curl -s -X POST "$BASE_URL/detect-confluence-trigger/run" -H "Content-Type: application/json" -d "{\"assets\": \"$ALPHA_ASSETS\"}" > "$OUT_DIR/sfp_triggers.json" &
curl -s -X POST "$BASE_URL/get-full-market-snapshot/run" -H "Content-Type: application/json" -d "{\"assets\": \"$ALPHA_ASSETS\"}" > "$OUT_DIR/alpha_snapshot.json" &

# ── 5. SPECIALIZED ETH ELE ────────────────────────────────────
echo "🛁 Running ETH ELE..."
curl -s -X POST "$BASE_URL/eth-ele-audit/run" -H "Content-Type: application/json" -d "{\"symbol\": \"$ETH_SYM\"}" > "$OUT_DIR/ele_potential.json" &

wait
echo "✅ ALL FLOWS IGNITED. Results in $OUT_DIR"

# Profile summary (v0.1)
echo "------------------------------------------------"
echo "PHD PROFILE SUMMARY:"
echo "Toxicity BTC: $(grep -o '"index":[0-9.]*' "$OUT_DIR/scalp_tox_btc.json" | cut -d: -f2)"
echo "Basis BTC:    $(grep -o '"basis_pct":[0-9.-]*' "$OUT_DIR/intraday_basis_btc.json" | cut -d: -f2)%"
echo "ELE Potential: $(grep -o '"transition_potential":"[^"]*"' "$OUT_DIR/ele_potential.json" | cut -d: -f2)"
echo "------------------------------------------------"
