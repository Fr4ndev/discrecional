import asyncio
import pandas as pd
import json
import logging
from strategies.zscore import ZScoreEngine
from core.config import TickerConfig

# Disable excessive logging
logging.getLogger("ZScore").setLevel(logging.WARNING)

async def main():
    engine = ZScoreEngine()
    
    print("Running HTF Z-Score Audit for BTC and ETH...")
    
    results = {}
    assets_to_audit = [
        {"symbol": "BTC/USDT", "name": "Bitcoin", "supply": 19690000},
        {"symbol": "ETH/USDT", "name": "Ethereum", "supply": 120000000}
    ]
    
    for asset in assets_to_audit:
        symbol = asset["symbol"]
        try:
            # engine._fetch_all_data handles multiple exchanges and timeframes
            data = await engine._fetch_all_data(symbol)
            if data and '1d' in data['price_data']:
                supply = data['supply'] or asset["supply"]
                df = engine._calculate_enhanced(data['price_data']['1d'], supply, data['cvd_data'], data['oi_data'])
                
                last = df.iloc[-1]
                results[symbol] = {
                    "z_score": round(float(last['mvrv_z_smooth']), 3),
                    "phase": str(last['wyckoff_phase']),
                    "signal": int(last['signal']),
                    "strength": int(last['signal_strength']),
                    "reason": str(last['signal_reason']),
                    "price": float(last['close'])
                }
            else:
                results[symbol] = {"error": "No daily data fetched"}
        except Exception as e:
            results[symbol] = {"error": str(e)}

    with open("htf_zscore_audit.json", "w") as f:
        json.dump(results, f, indent=2)
    print("HTF Audit Complete. Results saved to htf_zscore_audit.json")

if __name__ == "__main__":
    asyncio.run(main())
