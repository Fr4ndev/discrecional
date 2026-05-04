#!/bin/bash
cd "$(dirname "$0")/../.."
# CCXTV2 — Integrated Test Suite
# Runs all institutional microstructure unit tests.

echo "🧪 Starting CCXTV2 Integrated Test Suite..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Run tests in sequence
python3 tests/test_intelligence_hub.py
HU_RES=$?

python3 tests/test_funding_fees.py
FF_RES=$?

python3 tests/test_absorption.py
AB_RES=$?

python3 tests/test_zscore.py
ZS_RES=$?

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 TEST SUMMARY:"
[ $HU_RES -eq 0 ] && echo "✅ IntelligenceHub:  PASSED" || echo "❌ IntelligenceHub:  FAILED"
[ $FF_RES -eq 0 ] && echo "✅ FundingFees:      PASSED" || echo "❌ FundingFees:      FAILED"
[ $AB_RES -eq 0 ] && echo "✅ Absorption:       PASSED" || echo "❌ Absorption:       FAILED"
[ $ZS_RES -eq 0 ] && echo "✅ Z-Score Engine:   PASSED" || echo "❌ Z-Score Engine:   FAILED"

if [ $((HU_RES + FF_RES + AB_RES + ZS_RES)) -eq 0 ]; then
    echo "🎉 ALL SYSTEMS GO. Institutional architecture is healthy."
    exit 0
else
    echo "⚠️  SOME SYSTEMS FAILED. Check logs above."
    exit 1
fi
