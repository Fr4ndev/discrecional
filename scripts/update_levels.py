#!/usr/bin/env python3
"""
scripts/update_levels.py — Dynamic Level Generator
═══════════════════════════════════════════════════
Calcula automáticamente los niveles críticos (D1 High/Low, Weekly POC)
y los inyecta en data/watchlist_levels.json para que los daemons
los vigilen en tiempo real.

Uso sugerido: ejecutar via crontab cada 4 horas o manualmente.
"""

import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, "/home/wek/Escritorio/ccxtv2")
from core.data_engine import DataEngine

LEVELS_FILE = Path("/home/wek/Escritorio/ccxtv2/data/watchlist_levels.json")
ASSETS = [
    {"perp": "BTC/USDT:USDT", "name": "BTC"},
    {"perp": "ETH/USDT:USDT", "name": "ETH"},
]

async def update():
    engine = DataEngine()
    await engine.connect()
    
    current_data = {}
    if LEVELS_FILE.exists():
        try:
            current_data = json.loads(LEVELS_FILE.read_text())
        except:
            pass

    for asset in ASSETS:
        perp = asset["perp"]
        name = asset["name"]
        print(f"🔄 Calculando niveles para {name}...")
        
        # 1. Fetch D1 OHLCV (últimos 7 días)
        df = await engine.fetch_ohlcv(perp, "1d", limit=7)
        if df is None or df.empty:
            continue
            
        # Niveles D1 actual y anterior
        d1_high = float(df["high"].iloc[-1])
        d1_low  = float(df["low"].iloc[-1])
        pd_high = float(df["high"].iloc[-2]) # Previous Day
        pd_low  = float(df["low"].iloc[-2])
        
        # 2. Fetch H4 (para soportes/resistencias cercanas)
        df_h4 = await engine.fetch_ohlcv(perp, "4h", limit=10)
        h4_high = float(df_h4["high"].max())
        h4_low  = float(df_h4["low"].min())
        
        # Consolidar niveles
        # Usamos sets para evitar duplicados y luego ordenamos
        resistances = sorted(list(set([d1_high, pd_high, h4_high])))
        supports    = sorted(list(set([d1_low, pd_low, h4_low])), reverse=True)
        
        current_data[perp] = {
            "resistances": resistances,
            "supports": supports,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        print(f"   ✅ {name}: {len(resistances)} Resistencias | {len(supports)} Soportes")

    # Guardar en JSON
    LEVELS_FILE.write_text(json.dumps(current_data, indent=2))
    print(f"\n🚀 Watchlist de niveles actualizada en: {LEVELS_FILE}")
    
    await engine.close()

if __name__ == "__main__":
    asyncio.run(update())
