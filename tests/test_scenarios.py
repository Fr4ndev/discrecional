from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.bus import SignalBus
from core.signals import MarketSignal
from engine.synthesis_engine import HighConvictionAlert, SynthesisEngine


async def _publish(bus: SignalBus, source: str, symbol: str, signal_type: str, intensity: float, payload: dict) -> None:
    await bus.publish(
        MarketSignal(
            source=source,
            symbol=symbol,
            signal_type=signal_type,
            intensity=intensity,
            payload=payload,
            ts=datetime.now(timezone.utc),
        )
    )


async def run_scenarios() -> None:
    bus = SignalBus()
    alerts: list[HighConvictionAlert] = []

    async def on_alert(alert: HighConvictionAlert) -> None:
        alerts.append(alert)

    engine = SynthesisEngine(bus=bus, window_seconds=120, interest_threshold=1.5, on_alert=on_alert)
    await bus.start()
    await engine.start()

    # Scenario 1: Combo Institucional (direction aligned DOWN)
    await _publish(
        bus,
        source="sfp_advanced_monitor",
        symbol="BTC",
        signal_type="sfp_confirmed",
        intensity=0.9,
        payload={"sweep_type": "BEARISH", "timeframe": "5m", "price": 100000.0},
    )
    await _publish(
        bus,
        source="level_break_alert",
        symbol="BTC",
        signal_type="level_rejection_bear",
        intensity=0.7,
        payload={"timeframe": "5m", "price": 99900.0},
    )
    await asyncio.sleep(0.05)
    await _publish(
        bus,
        source="whale_sentinel",
        symbol="BTC",
        signal_type="whale_sell",
        intensity=1.0,
        payload={"timeframe": "trade_tick", "usd_value": 1200000.0},
    )
    await asyncio.sleep(0.05)

    # Scenario 2: Combo Squeeze
    await _publish(
        bus,
        source="squeeze_watcher",
        symbol="ETH",
        signal_type="squeeze_high_conviction",
        intensity=0.95,
        payload={"timeframe": "20s_loop", "price": 3000.0},
    )
    await _publish(
        bus,
        source="opportunity_sentinel",
        symbol="ETH",
        signal_type="obi_flip_bull",
        intensity=0.65,
        payload={"timeframe": "15s_loop", "price": 3002.0},
    )
    await asyncio.sleep(0.05)
    await _publish(
        bus,
        source="ignition_daemon",
        symbol="ETH",
        signal_type="coordinated_ignition_up",
        intensity=0.9,
        payload={"timeframe": "30s_loop", "btc_obi": 0.5, "eth_obi": 0.45},
    )
    await asyncio.sleep(0.05)

    # Scenario 3: Combo Breakout
    await _publish(
        bus,
        source="level_break_alert",
        symbol="BTC",
        signal_type="level_breakout_up",
        intensity=0.72,
        payload={"timeframe": "5m", "price": 101000.0},
    )
    await _publish(
        bus,
        source="opportunity_sentinel",
        symbol="BTC",
        signal_type="cvd_flip_bull",
        intensity=0.65,
        payload={"timeframe": "15s_loop", "price": 101050.0},
    )
    await asyncio.sleep(0.05)

    # Scenario 4: Interest increment threshold
    await _publish(
        bus,
        source="opportunity_sentinel",
        symbol="SOL",
        signal_type="obi_flip_bull",
        intensity=0.8,
        payload={"timeframe": "15s_loop", "price": 210.0},
    )
    await _publish(
        bus,
        source="opportunity_sentinel",
        symbol="SOL",
        signal_type="cvd_flip_bull",
        intensity=0.8,
        payload={"timeframe": "15s_loop", "price": 211.0},
    )
    await asyncio.sleep(0.05)

    combos = {a.combo for a in alerts}
    assert "combo_institucional" in combos, "Missing institutional combo alert"
    assert "the_institutional_whale" in combos, "Missing institutional whale combo alert"
    assert "combo_squeeze" in combos, "Missing squeeze combo alert"
    assert "combo_breakout" in combos, "Missing breakout combo alert"
    assert "global_ignition" in combos, "Missing global ignition combo alert"
    assert "interes_incrementado" in combos, "Missing interest increment alert"

    await bus.stop()
    print("OK: all synthesis scenarios passed")


if __name__ == "__main__":
    asyncio.run(run_scenarios())
