import asyncio
import os
import sys
import io

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config import settings
from core.data_engine import DataEngine
from strategies.zscore import ZScoreEngine

async def test_zscore():
    print("🚀 Starting ZScoreEngine Unit Test...")
    engine = DataEngine()
    z_engine = ZScoreEngine()
    
    # Use first ticker from universe (BTC)
    ticker = settings.universe[0]
    print(f"\n[Test 1] Running Z-Score for {ticker.name}...")
    
    try:
        # Connect engine (DataEngine shim)
        await engine.connect()
        
        # Run Z-Score
        result = await z_engine.run(ticker, engine)
        
        if result:
            buf, caption = result
            print("✅ Z-Score: PASSED")
            print(f"   • Caption: {caption}")
            
            # Save chart for visual verification
            chart_path = os.path.abspath("tests/zscore_test_chart.png")
            with open(chart_path, "wb") as f:
                f.write(buf.getbuffer())
            print(f"   • Chart saved to: {chart_path}")
        else:
            print("❌ Z-Score: FAILED (No result returned)")
            
    except Exception as e:
        print(f"❌ Z-Score: FAILED ({e})")
    finally:
        await engine.close()

    print("\n🎉 ZScoreEngine tests complete!")

if __name__ == "__main__":
    asyncio.run(test_zscore())
