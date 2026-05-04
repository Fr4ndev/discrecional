import asyncio
import os
import sys
import pandas as pd

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from strategies.funding_fees import FundingFeesEngine

async def test_funding_engine():
    print("🚀 Starting FundingFeesEngine Unit Test...")
    engine = FundingFeesEngine()
    
    # Test 1: Fetching (CCXT fallback should work)
    print("\n[Test 1] Fetching Funding Fees...")
    df = await engine.fetch_funding_fees()
    if not df.empty:
        print(f"✅ Fetching: PASSED ({len(df)} assets found)")
        print(df.head())
    else:
        print("❌ Fetching: FAILED")
        return

    # Test 2: Detect Variances (Manual injection)
    print("\n[Test 2] Variance Detection...")
    # Mock a current DF
    current_data = pd.DataFrame([
        {"asset": "BTC", "binance": 0.07, "bybit": 0.05},
        {"asset": "ETH", "binance": -0.02, "bybit": -0.02}
    ])
    
    # Pre-populate "last_rates" to ensure variance
    engine._save_last_rates(
        rates={"BTC": {"binance": 0.01}, "ETH": {"binance": -0.01}},
        history={}
    )
    
    anomalies = engine.detect_variances(current_data)
    if any(a["symbol"] == "BTC" for a in anomalies):
        print("✅ Variance Detection: PASSED")
    else:
        print("❌ Variance Detection: FAILED (No anomaly detected)")

    print("\n🎉 FundingFeesEngine tests complete!")

if __name__ == "__main__":
    asyncio.run(test_funding_engine())
