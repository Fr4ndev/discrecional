#!/bin/bash
# ignite_all_flows_v2.sh — Senior Desk Total Ignition (Unified Action-Server v2.0)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# This version uses modernized Composite Actions instead of direct atomic curls.

# ── CONFIGURATION ──────────────────────────────────────────────
BASE_URL="http://localhost:8080/api/actions/funding-action-server"
DATA_DIR="/home/wek/Escritorio/ccxtv2/data/snapshots"
mkdir -p "$DATA_DIR"

ASSETS="BTC,ETH"
ALPHA_ASSETS="BTC,ETH,SOL,HYPE"

echo "🚀 IGNITING SENIOR DESK COMPOSITE FLOWS..."

# ── 1. FLOW-SCALP (Toxicity + Microstructure + Walls) ──────────
echo "⚡ Running Composite FLOW-SCALP (BTC,ETH)..."
curl -s -X POST "$BASE_URL/run-scalp-workflow/run" \
     -H "Content-Type: application/json" \
     -d "{\"assets\": \"$ASSETS\"}" > "$DATA_DIR/full_scalp_snapshot.json" &

# ── 2. FLOW-INTRADAY (Basis + Tactical + UDC) ──────────────────
echo "📅 Running Composite FLOW-INTRADAY (BTC,ETH)..."
curl -s -X POST "$BASE_URL/run-intraday-workflow/run" \
     -H "Content-Type: application/json" \
     -d "{\"assets\": \"$ASSETS\"}" > "$DATA_DIR/full_intraday_snapshot.json" &

# ── 3. FLOW-SFP (Institutional Reversal) ───────────────────────
echo "🔥 Running Composite SFP-FLOW (BTC,ETH)..."
curl -s -X POST "$BASE_URL/detect-sfp-confluence/run" \
     -H "Content-Type: application/json" \
     -d "{\"assets\": \"$ASSETS\"}" > "$DATA_DIR/full_sfp_snapshot.json" &

# ── 4. ALPHA UNIVERSE (Multi-Ticker Snapshot) ──────────────────
echo "🏗️  Running ALPHA UNIVERSE Audit ($ALPHA_ASSETS)..."
curl -s -X POST "$BASE_URL/senior-desk-universe-audit/run" \
     -H "Content-Type: application/json" \
     -d "{\"assets\": \"$ALPHA_ASSETS\"}" > "$DATA_DIR/full_alpha_snapshot.json" &

# ── 5. SPECIALIZED ETH ELE ────────────────────────────────────
echo "🛁 Running ETH ELE Specialized Audit..."
curl -s -X POST "$BASE_URL/eth-ele-audit/run" \
     -H "Content-Type: application/json" \
     -d "{\"symbol\": \"ETH/USDT:USDT\"}" > "$DATA_DIR/full_ele_snapshot.json" &

wait
echo "✅ ALL COMPOSITE FLOWS IGNITED."
echo "📂 Snapshots archived in $DATA_DIR"

# ── SUMMARY ───────────────────────────────────────────────────
# Note: The output structure differs from V1. V2 leverages the unified 
# IntelligenceHub scoring and formatting.
echo "------------------------------------------------"
echo "PHD SYSTEM STATE (v2.0):"
echo "Check data/snapshots/ for full institutional dossiers."
echo "------------------------------------------------"
