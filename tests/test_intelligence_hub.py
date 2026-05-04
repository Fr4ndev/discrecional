import asyncio
import os
import sys
import time

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.Core_Intelligence_Hub import IntelligenceHub

async def run_tests():
    print("🚀 Starting IntelligenceHub Unit Tests...")
    
    # Test 1: Singleton
    print("\n[Test 1] Singleton Check...")
    hub1 = await IntelligenceHub.instance()
    hub2 = await IntelligenceHub.instance()
    if hub1 is hub2:
        print("✅ Singleton: PASSED")
    else:
        print("❌ Singleton: FAILED")
        return

    # Test 2: Connection
    print("\n[Test 2] Exchange Connection...")
    try:
        await hub1.connect()
        if hub1._exchange is not None:
            print(f"✅ Connection: PASSED (Exchange: {hub1._exchange.id})")
        else:
            print("❌ Connection: FAILED (Exchange is None)")
            return
    except Exception as e:
        print(f"❌ Connection: FAILED ({e})")
        return

    # Test 3: Market Snapshot
    print("\n[Test 3] Market Snapshot (Real-time data)...")
    try:
        start_t = time.time()
        snapshot = await hub1.market_snapshot("BTC/USDT:USDT")
        end_t = time.time()
        
        if snapshot and snapshot.price > 0:
            print(f"✅ Snapshot: PASSED")
            print(f"   • Price: {snapshot.price}")
            print(f"   • OBI: {snapshot.obi.obi}")
            print(f"   • Verdict: {snapshot.toxicity.senior_verdict if snapshot.toxicity else 'N/A'}")
            print(f"   • Latency: {end_t - start_t:.2f}s")
        else:
            print("❌ Snapshot: FAILED (Empty or invalid snapshot)")
    except Exception as e:
        print(f"❌ Snapshot: FAILED ({e})")

    # Test 4: TTL Cache
    print("\n[Test 4] TTL Cache Check...")
    print(f"   • {hub1.cache_stats}")
    
    await hub1.close()
    print("\n🎉 All tests complete!")

if __name__ == "__main__":
    asyncio.run(run_tests())
