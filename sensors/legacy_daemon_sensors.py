from __future__ import annotations

import re
from typing import Optional

from sensors.base import LogTailSensor

ASSET_RE = re.compile(r"\b(BTC|ETH|SOL|TAO|LINK|HYPE)\b")


def infer_asset(line: str, fallback: str = "GENERIC") -> str:
    m = ASSET_RE.search(line.upper())
    return m.group(1) if m else fallback


class WhaleSensor(LogTailSensor):
    async def handle_line(self, line: str) -> None:
        if "WHALE" in line.upper():
            await self.publish("whale_activity", infer_asset(line), 0.65, {"raw": line})


class SpoofSensor(LogTailSensor):
    async def handle_line(self, line: str) -> None:
        if "SPOOF ALERT" in line.upper():
            await self.publish("liquidity_spoof", infer_asset(line), 0.72, {"raw": line})


class IgnitionSensor(LogTailSensor):
    async def handle_line(self, line: str) -> None:
        upper = line.upper()
        if "IGNITION" in upper or "DUMP" in upper or "ETH_LEAD" in upper or "BTC_LEAD" in upper:
            await self.publish("cross_asset_ignition", infer_asset(line, "BTC"), 0.68, {"raw": line})


class VolumeSensor(LogTailSensor):
    async def handle_line(self, line: str) -> None:
        upper = line.upper()
        if "BULLISH CONVICTION" in upper or "BEARISH DISTRIBUTION" in upper:
            await self.publish("volume_imbalance", infer_asset(line), 0.6, {"raw": line})


class ScalpSensor(LogTailSensor):
    async def handle_line(self, line: str) -> None:
        if "NEW ALERT FOR" in line.upper():
            await self.publish("scalp_trigger", infer_asset(line), 0.7, {"raw": line})


class OpportunitySensor(LogTailSensor):
    async def handle_line(self, line: str) -> None:
        if "ALERT" in line.upper():
            await self.publish("opportunity_flip", infer_asset(line), 0.75, {"raw": line})


class LevelBreakSensor(LogTailSensor):
    async def handle_line(self, line: str) -> None:
        upper = line.upper()
        if "BREAKOUT" in upper or "REJECTION" in upper:
            await self.publish("level_event", infer_asset(line), 0.74, {"raw": line})


class SqueezeSensor(LogTailSensor):
    async def handle_line(self, line: str) -> None:
        upper = line.upper()
        if "ALERTA HC SQUEEZE" in upper or "SQUEEZE WARNING" in upper:
            conf = 0.9 if "HC" in upper else 0.65
            await self.publish("squeeze_condition", infer_asset(line, "ETH"), conf, {"raw": line})


class SFPAdvancedSensor(LogTailSensor):
    async def handle_line(self, line: str) -> None:
        if "SIGNAL" in line.upper():
            await self.publish("sfp_signal", infer_asset(line), 0.85, {"raw": line})
