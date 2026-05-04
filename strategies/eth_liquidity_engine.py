import ccxt
import time
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.Core_Intelligence_Hub import IntelligenceHub
from strategies.zscore import ZScoreEngine

class ETHLiquidityEngine:
    """
    ETH Liquidity Engine (ELE)
    High-probability scalp entry with Intraday transition logic.
    Focuses on SFP + Microstructure (OBI/Pulse/Whale) + Basis.
    """
    def __init__(self, symbol="ETH/USDT:USDT", engine=None):
        self.symbol = symbol
        self.engine = engine or IntelligenceHub.instance_sync()
        self.levels = {}
        self.last_sfp_time = 0
        self.cooldown = 300 # 5 minutes between SFP alerts

    async def connect(self):
        self.engine._init_internals()
        await self.engine.connect()

    async def fetch_key_levels(self):
        """Fetches Daily and 4H High/Low levels"""
        # Daily
        ohlcv_1d = await self.engine.fetch_ohlcv(self.symbol, '1d', limit=2)
        if ohlcv_1d is not None and not ohlcv_1d.empty:
            self.levels['daily_high'] = float(ohlcv_1d['high'].iloc[-2])
            self.levels['daily_low'] = float(ohlcv_1d['low'].iloc[-2])
        
        # 4H
        ohlcv_4h = await self.engine.fetch_ohlcv(self.symbol, '4h', limit=3)
        if ohlcv_4h is not None and not ohlcv_4h.empty:
            self.levels['h4_high'] = float(ohlcv_4h['high'].iloc[-2])
            self.levels['h4_low'] = float(ohlcv_4h['low'].iloc[-2])
            
        return self.levels

    async def get_basis(self):
        """Calculates Spot-Perp Basis %"""
        spot_sym = self.symbol.split(":")[0] if ":" in self.symbol else self.symbol
        spot_ticker = await self.engine.fetch_ticker(spot_sym)
        perp_ticker = await self.engine.fetch_ticker(self.symbol)
        
        if spot_ticker and perp_ticker:
            spot_p = float(spot_ticker['last'])
            perp_p = float(perp_ticker['last'])
            basis_pct = ((perp_p - spot_p) / spot_p) * 100
            return basis_pct
        return None

    async def run_audit(self):
        """Main Loop for the ELE Strategy"""
        await self.fetch_key_levels()
        ticker = await self.engine.fetch_ticker(self.symbol)
        curr_p = float(ticker['last'])
        
        # SFP Detection Trigger
        signal = None
        hit_level = None
        
        if curr_p > self.levels.get('daily_high', 0) or curr_p > self.levels.get('h4_high', 0):
            signal = "SHORT_SFP"
            hit_level = max(self.levels.get('daily_high', 0), self.levels.get('h4_high', 0))
        elif curr_p < self.levels.get('daily_low', 999999) or curr_p < self.levels.get('h4_low', 999999):
            signal = "LONG_SFP"
            hit_level = min(self.levels.get('daily_low', 999999), self.levels.get('h4_low', 999999))

        if signal and (time.time() - self.last_sfp_time > self.cooldown):
            # 1. Microstructure Check (OBI)
            ob = await self.engine.fetch_order_book(self.symbol, limit=20)
            bids = sum(b[1] for b in ob.get('bids', []))
            asks = sum(a[1] for a in ob.get('asks', []))
            obi = (bids - asks) / (bids + asks) if (bids+asks)>0 else 0
            
            # 2. Basis Check
            basis = await self.get_basis()
            
            # 3. Z-Score (Statistical Mean Reversion)
            z_engine = ZScoreEngine(self.engine)
            # Simulating Z-score for brevity, in reality we'd pull from zscore_engine
            z_score = 0.0 # Placeholder
            
            # 4. Filter Logic
            conviction = "LOW"
            if signal == "LONG_SFP":
                if obi > 0.40 and basis > 0: conviction = "HIGH"
                elif obi > 0.20: conviction = "MEDIUM"
            else: # SHORT_SFP
                if obi < -0.40 and basis < 0.02: conviction = "HIGH" # Assuming short on lower basis is more premium
                elif obi < -0.20: conviction = "MEDIUM"

            if conviction != "LOW":
                print(f"🔥 [{signal}] | Level: {hit_level} | Price: {curr_p} | Conviction: {conviction}")
                print(f"   📊 OBI: {round(obi, 3)} | Basis: {round(basis, 4)}%")
                self.last_sfp_time = time.time()
                
                # Transition Logic: If Basis is extremely favorable, flag for Intraday
                if conviction == "HIGH" and abs(basis) > 0.05:
                    print("   🚀 [INTRADAY TRANSITION] Basis trend confirms high-conviction continuation.")

    async def run(self):
        await self.connect()
        while True:
            try:
                await self.run_audit()
            except Exception as e:
                print(f"Error in ELE Loop: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    engine = ETHLiquidityEngine()
    asyncio.run(engine.run())
