#!/bin/bash
cd "$(dirname "$0")/../.."
# run_full_audit.sh — Integrated Full Market Audit Routine
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo "🚀 Starting FULL MARKET AUDIT..."

# 1. Scalp Flow (Microstructure)
./scripts/routines/run_scalp_workflow.sh

# 2. Intraday Flow (Session Capture)
./scripts/routines/run_intraday_workflow.sh

# 3. ELE Audit (ETH Transition)
./scripts/routines/run_ele_routine.sh

echo "✅ FULL MARKET AUDIT complete."
