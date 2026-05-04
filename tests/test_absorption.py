import asyncio
import os
import sys
import json

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.Core_Intelligence_Hub import IntelligenceHub
from funding_action_server.actions.absorption_detector import AbsorptionDetector

async def test_absorption():
    print("🚀 Starting AbsorptionDetector Unit Test...")
    hub = await IntelligenceHub.instance()
    await hub.connect()
    detector = AbsorptionDetector(hub)
    
    # Test 1: Full Scan on BTC
    print("\n[Test 1] Scanning BTC/USDT:USDT...")
    try:
        result = await detector.scan("BTC/USDT:USDT")
        print("✅ Scan: PASSED")
        print(f"   • Price: {result.price}")
        print(f"   • AR: {result.absorption_rate:.4f} ({result.absorption_verdict})")
        print(f"   • Iceberg: {result.iceberg_score:.4f} (Side: {result.iceberg_side})")
        print(f"   • Toxicity: {result.toxicity_index:.4f} ({result.toxicity_verdict})")
        print(f"   • Kyle's Lambda: {result.kyles_lambda:.6f} ({result.market_quality})")
    except Exception as e:
        print(f"❌ Scan: FAILED ({e})")

    # Test 2: Verify logic with manual data injection (if possible)
    # Since detector.scan uses hub.fetch_trades, we'd need to mock the hub.
    
    await hub.close()
    print("\n🎉 AbsorptionDetector tests complete!")

if __name__ == "__main__":
    asyncio.run(test_absorption())
