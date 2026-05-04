import asyncio
import time
from core.data_engine import DataEngine

class ExecutionEngine:
    def __init__(self, slip_threshold=0.0015):
        self.slip_threshold = slip_threshold

    async def estimate_slippage(self, symbol, side, amount_usd):
        engine = DataEngine()
        await engine.connect()
        try:
            ob = await engine.fetch_order_book(symbol, limit=100)
            ticker = await engine.fetch_ticker(symbol)
            mid_price = ticker['last']
            
            levels = ob['asks'] if side == 'buy' else ob['bids']
            
            accumulated_qty = 0
            filled_usd = 0
            
            for price, qty in levels:
                level_usd = price * qty
                if filled_usd + level_usd >= amount_usd:
                    remaining_usd = amount_usd - filled_usd
                    accumulated_qty += remaining_usd / price
                    filled_usd = amount_usd
                    break
                else:
                    accumulated_qty += qty
                    filled_usd += level_usd
            
            if filled_usd < amount_usd:
                return 1.0 # Infinite slippage (Not enough liquidity)
                
            avg_price = filled_usd / accumulated_qty
            slippage = abs(avg_price - mid_price) / mid_price
            return slippage
            
        finally:
            await engine.close()

    async def predatory_execute(self, symbol, side, total_amount_usd):
        slip = await self.estimate_slippage(symbol, side, total_amount_usd)
        
        if slip > self.slip_threshold:
            print(f"⚠️ High Slippage Detected ({slip*100:.4f}%). Activating Micro-TWAP (5 fragments).")
            fragment_usd = total_amount_usd / 5
            for i in range(5):
                print(f"Executing Fragment {i+1}/5: {fragment_usd} USD")
                # actual execution would happen here: await self.place_market_order(...)
                await asyncio.sleep(0.5) # Micro-spacing
        else:
            print(f"✅ Liquidity Optimal ({slip*100:.4f}%). Executing Single MARKET IGNITION.")
            # actual execution: await self.place_market_order(...)

class DynamicTrailingStop:
    def __init__(self, activation_price, trail_pct=0.005):
        self.activation_price = activation_price
        self.trail_pct = trail_pct
        self.active = False
        self.peak_price = 0

    def update(self, current_price):
        if not self.active and current_price >= self.activation_price:
            self.active = True
            self.peak_price = current_price
            print(f"🎯 Dynamic Trailing Stop ACTIVATED @ {current_price}")
            
        if self.active:
            if current_price > self.peak_price:
                self.peak_price = current_price
            
            stop_price = self.peak_price * (1 - self.trail_pct)
            if current_price <= stop_price:
                return "EXIT_NOW"
        return "HOLD"

class LiquidityAwareStopLoss:
    def __init__(self, entry_price, symbol, tox_index, slippage_real):
        self.entry_price = entry_price
        self.symbol = symbol
        self.tox_index = tox_index
        self.slippage_real = slippage_real
        self.sl_price = 0
        self.breakeven_activated = False
        self.base_url = "http://localhost:8080/api/actions/funding-action-server"

    async def initialize(self):
        # 1. Fetch UDC Walls
        import httpx
        import json
        async with httpx.AsyncClient() as client:
            try:
                asset = self.symbol.split("/")[0]
                resp = await client.post(f"{self.base_url}/get-ultra-deep-confluence/run", 
                                       json={"assets": asset, "depth": 100}, timeout=20)
                # IMP-05 (Cycle 5): Safe double-decode — Action Server may return dict or JSON string
                raw = resp.json()
                if isinstance(raw, str):
                    data = json.loads(raw)
                else:
                    data = raw
                
                # Find nearest institutional support
                supports = data.get("top_supports_bids", [])
                if supports:
                    # SL is 2 ticks below nearest wall
                    nearest_wall = supports[0]['price']
                    self.sl_price = nearest_wall - 2 # Assuming 1.0 tick size for simplicity or fetch tick size
                    
                    # 2. Volatility Filter: Expand 15% if Toxicity > 0.70
                    if self.tox_index > 0.70:
                        risk_distance = self.entry_price - self.sl_price
                        self.sl_price -= (risk_distance * 0.15)
                        print(f"⚠️ Volatility Detected (Tox: {self.tox_index:.2f}). SL expanded by 15%.")
                else:
                    # Fallback to fixed 1%
                    self.sl_price = self.entry_price * 0.99
            except:
                self.sl_price = self.entry_price * 0.99
        
        print(f"🛡️ Liquidity-Aware SL Set @ {self.sl_price:.2f} (Institutional Guard)")

    def update(self, current_price):
        # 3. Aggressive Breakeven: Price > 1.5 * slippage_real
        move_threshold = self.entry_price * (1 + (self.slippage_real * 1.5))
        
        if not self.breakeven_activated and current_price >= move_threshold:
            self.sl_price = self.entry_price
            self.breakeven_activated = True
            print(f"⚡ AGGRESSIVE BREAKEVEN: SL moved to entry ({self.entry_price})")

        if current_price <= self.sl_price:
            return "EXIT_NOW"
        return "HOLD"
