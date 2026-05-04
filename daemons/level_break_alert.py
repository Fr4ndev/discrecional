#!/usr/bin/env python3
"""
daemons/level_break_alert.py — Level Break Alert v1.0
═══════════════════════════════════════════════════════
Daemon de vigilancia de ruptura, retest y rechazo de niveles
críticos para BTC y ETH. Poll agresivo cada 10s.

Tipos de alerta:
  - BREAKOUT: precio rompe nivel con vela M5 cerrando al otro lado
  - RETEST:   precio regresa a nivel roto (opportunity)
  - REJECTION: precio toca nivel, vela M5 cierra de regreso (SFP)

Los niveles se cargan desde data/watchlist_levels.json (editable en caliente).

Uso:
    python3 -u daemons/level_break_alert.py > data/level_break_alert.log 2>&1 &
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import requests

sys.path.insert(0, "/home/wek/Escritorio/ccxtv2")

from core.config import settings
from core.data_engine import DataEngine
from alerts.telegram import TelegramService

# ── Config ────────────────────────────────────────────────────────
ASSETS = [
    {"perp": "BTC/USDT:USDT", "spot": "BTC/USDT", "name": "BTC"},
    {"perp": "ETH/USDT:USDT", "spot": "ETH/USDT", "name": "ETH"},
]
POLL_INTERVAL    = 10     # segundos — agresivo
COOLDOWN_PER_LVL = 1200  # 20 min por nivel
LEVEL_PROX_PCT   = 0.002  # 0.2% — toca el nivel
VOL_CONFIRM_RATIO = 0.5   # volumen debe ser > 50% del promedio H1

DATA_DIR   = Path("/home/wek/Escritorio/ccxtv2/data")
LOG_FILE   = DATA_DIR / "level_break_alert.log"
LEVELS_FILE = DATA_DIR / "watchlist_levels.json"
HBEAT_FILE = DATA_DIR / "levelbreak_hbeat.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(str(LOG_FILE))],
)
logger = logging.getLogger("LevelBreakAlert")


class LevelState(str, Enum):
    ABOVE  = "ABOVE"
    BELOW  = "BELOW"
    AT     = "AT"


def _send_telegram(text: str) -> None:
    token = settings.telegram_token
    chat  = settings.chat_id
    topic = int(settings.topic_id) if settings.topic_id else None
    if not token or not chat:
        logger.info(f"[Mock Telegram] {text[:120]}")
        return
    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    body = {"chat_id": chat, "text": text, "parse_mode": "Markdown"}
    if topic:
        body["message_thread_id"] = topic
    try:
        requests.post(url, json=body, timeout=5)
    except Exception as e:
        logger.error(f"Telegram: {e}")


def _load_levels() -> dict:
    try:
        with open(LEVELS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


@dataclass
class LevelTracker:
    level: float
    kind:  str   # "resistance" or "support"
    last_state:  str   = "UNKNOWN"  # ABOVE / BELOW
    last_alert:  float = 0.0
    broke_at:    float = 0.0  # timestamp cuando se rompió

    def cooled(self) -> bool:
        return (time.time() - self.last_alert) > COOLDOWN_PER_LVL


@dataclass
class AssetLevelState:
    name: str
    perp: str
    trackers: Dict[float, LevelTracker] = field(default_factory=dict)
    avg_h1_vol: float = 0.0

    def sync_levels(self, levels_data: dict) -> None:
        """Sync trackers with the current watchlist JSON."""
        all_levels = {}
        for lvl in levels_data.get("resistances", []):
            all_levels[float(lvl)] = "resistance"
        for lvl in levels_data.get("supports", []):
            all_levels[float(lvl)] = "support"

        # Add new levels
        for lvl, kind in all_levels.items():
            if lvl not in self.trackers:
                self.trackers[lvl] = LevelTracker(level=lvl, kind=kind)

        # Remove stale levels
        for lvl in list(self.trackers.keys()):
            if lvl not in all_levels:
                del self.trackers[lvl]


class LevelBreakAlert:

    def __init__(self):
        self.engine   = DataEngine()
        self.tg       = TelegramService()
        self._running = True
        self._cycles  = 0
        self.states: Dict[str, AssetLevelState] = {
            a["perp"]: AssetLevelState(name=a["name"], perp=a["perp"])
            for a in ASSETS
        }

    async def run(self) -> None:
        logger.info("📍 Level Break Alert v1.0 — INICIADO")
        logger.info(f"   Activos: BTC + ETH | Poll: {POLL_INTERVAL}s | Cooldown: {COOLDOWN_PER_LVL//60}min/nivel")
        await self.engine.connect()
        # Cargar volumen promedio inicial
        await self._init_volumes()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._stop)

        try:
            await self._main_loop()
        finally:
            await self.engine.close()
            logger.info("🛑 Level Break Alert detenido.")

    def _stop(self) -> None:
        self._running = False

    async def _init_volumes(self) -> None:
        """Precalculate average H1 volume per asset."""
        for asset in ASSETS:
            df = await self.engine.fetch_ohlcv(asset["perp"], "1h", limit=10)
            if df is not None and not df.empty:
                self.states[asset["perp"]].avg_h1_vol = float(df["volume"].astype(float).mean())
                logger.info(f"📊 {asset['name']} avg H1 vol: {self.states[asset['perp']].avg_h1_vol:.2f}")

    async def _get_price_and_obi(self, perp: str) -> tuple[float, float, float]:
        """Returns (price, obi, last_m5_close)"""
        t  = await self.engine.fetch_ticker(perp)
        price = float(t["last"]) if t else 0.0

        ob = await self.engine.fetch_order_book(perp, limit=20)
        obi = 0.0
        if ob:
            bq = sum(b[1] for b in ob.get("bids", []))
            aq = sum(a[1] for a in ob.get("asks", []))
            obi = (bq - aq) / (bq + aq) if (bq + aq) > 0 else 0.0

        # M5 last close (para confirmar breakout/rejection)
        df_m5 = await self.engine.fetch_ohlcv(perp, "5m", limit=3)
        m5_close = float(df_m5["close"].iloc[-2]) if df_m5 is not None and len(df_m5) >= 2 else price

        return price, round(obi, 4), m5_close

    def _format_breakout(self, name: str, level: float, price: float, obi: float,
                         direction: str, kind: str) -> str:
        emoji = "🔴" if direction == "DOWN" else "🟢"
        label = "SOPORTE ROTO" if (direction == "DOWN" and kind == "support") else \
                "RESISTENCIA SUPERADA" if (direction == "UP" and kind == "resistance") else \
                f"RUPTURA {direction}"
        tp_mult = 0.015 if name == "BTC" else 0.012
        tp1 = price * (1 - tp_mult) if direction == "DOWN" else price * (1 + tp_mult)
        tp2 = price * (1 - tp_mult * 2) if direction == "DOWN" else price * (1 + tp_mult * 2)
        sl  = price * (1 + 0.006) if direction == "DOWN" else price * (1 - 0.006)

        return (
            f"{emoji} *{label} — {name}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔑 Nivel: `${level:,.2f}` | Precio: `${price:,.2f}`\n"
            f"📊 OBI: `{obi:+.3f}` | Dir: `{direction}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Entry: `${price:,.2f}`\n"
            f"💰 TP1: `${tp1:,.2f}` | TP2: `${tp2:,.2f}`\n"
            f"🛡️ SL: `${sl:,.2f}`\n"
            f"⏰ {datetime.now(timezone.utc).strftime('%H:%M UTC')}"
        )

    def _format_rejection(self, name: str, level: float, price: float, obi: float,
                          kind: str, direction_rejected: str) -> str:
        emoji = "🔄"
        setup = "SHORT SFP" if direction_rejected == "UP" else "LONG SFP"
        tp_mult = 0.012 if name == "BTC" else 0.010
        tp1 = price * (0.987 if direction_rejected == "UP" else 1.010)
        sl  = level * (1.003 if direction_rejected == "UP" else 0.997)

        return (
            f"{emoji} *RECHAZO (SFP) — {name} {setup}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔑 Nivel: `${level:,.2f}` | Precio: `${price:,.2f}`\n"
            f"📊 OBI: `{obi:+.3f}` | Rechazado desde: {kind}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Setup {setup}\n"
            f"💰 TP1: `${tp1:,.2f}`\n"
            f"🛡️ SL: `${sl:,.2f}` (sobre nivel)\n"
            f"⏰ {datetime.now(timezone.utc).strftime('%H:%M UTC')}"
        )

    async def _emit_level_signal(
        self,
        signal_type: str,
        state: AssetLevelState,
        level: float,
        price: float,
        obi: float,
        message: str,
    ) -> None:
        await self.tg.send_text(message)

    async def _scan_asset(self, asset: dict, all_levels: dict) -> None:
        perp  = asset["perp"]
        state = self.states[perp]

        # Sync niveles desde JSON (permite hot-reload)
        state.sync_levels(all_levels.get(perp, {}))
        if not state.trackers:
            return

        price, obi, m5_close = await self._get_price_and_obi(perp)
        if price == 0.0:
            return

        for level, tracker in state.trackers.items():
            if not tracker.cooled():
                continue

            prox = abs(price - level) / level

            # Determinar estado anterior
            prev_state = tracker.last_state
            curr_above = price > level

            # Actualizar estado
            if prox < LEVEL_PROX_PCT:
                curr_str = "AT"
            elif curr_above:
                curr_str = "ABOVE"
            else:
                curr_str = "BELOW"

            # ── BREAKOUT ──────────────────────────────────────────
            if prev_state == "ABOVE" and curr_str == "BELOW":
                # Precio cayó a través del nivel
                if m5_close < level:  # M5 cerró bajo el nivel → confirmado
                    msg = self._format_breakout(state.name, level, price, obi, "DOWN", tracker.kind)
                    logger.info(f"🔴 BREAKOUT DOWN [{state.name}] nivel ${level:,.2f}")
                    await self._emit_level_signal("level_breakout_down", state, level, price, obi, msg)
                    tracker.last_alert = time.time()
                    tracker.broke_at   = time.time()

            elif prev_state == "BELOW" and curr_str == "ABOVE":
                # Precio subió a través del nivel
                if m5_close > level:  # M5 cerró sobre el nivel → confirmado
                    msg = self._format_breakout(state.name, level, price, obi, "UP", tracker.kind)
                    logger.info(f"🟢 BREAKOUT UP [{state.name}] nivel ${level:,.2f}")
                    await self._emit_level_signal("level_breakout_up", state, level, price, obi, msg)
                    tracker.last_alert = time.time()
                    tracker.broke_at   = time.time()

            # ── REJECTION (SFP) ───────────────────────────────────
            elif curr_str == "AT":
                # Precio está en la zona del nivel
                # Rechazo bearish: tocó resistencia, M5 cierra de regreso
                if tracker.kind == "resistance" and prev_state in ("ABOVE", "AT"):
                    if m5_close < level and obi < -0.20:
                        msg = self._format_rejection(state.name, level, price, obi, "resistance", "UP")
                        logger.info(f"🔄 REJECTION BEARISH [{state.name}] nivel ${level:,.2f}")
                        await self._emit_level_signal("level_rejection_bear", state, level, price, obi, msg)
                        tracker.last_alert = time.time()

                # Rechazo bullish: tocó soporte, M5 cierra de regreso
                elif tracker.kind == "support" and prev_state in ("BELOW", "AT"):
                    if m5_close > level and obi > 0.20:
                        msg = self._format_rejection(state.name, level, price, obi, "support", "DOWN")
                        logger.info(f"🔄 REJECTION BULLISH [{state.name}] nivel ${level:,.2f}")
                        await self._emit_level_signal("level_rejection_bull", state, level, price, obi, msg)
                        tracker.last_alert = time.time()

            tracker.last_state = curr_str
            logger.debug(f"[{state.name}] Nivel ${level:,.2f} | Estado: {prev_state}→{curr_str} | OBI={obi:+.3f}")

    async def _main_loop(self) -> None:
        # Actualizar vol promedio cada 60 ciclos (10min)
        vol_refresh = 0

        while self._running:
            self._cycles += 1

            try:
                if vol_refresh == 0:
                    await self._init_volumes()
                vol_refresh = (vol_refresh + 1) % 60

                levels = _load_levels()
                await asyncio.gather(*[self._scan_asset(a, levels) for a in ASSETS])

                # Heartbeat
                if self._cycles % 30 == 0:
                    HBEAT_FILE.write_text(json.dumps({
                        "ts":     datetime.now(timezone.utc).isoformat(),
                        "cycles": self._cycles,
                        "status": "ALIVE",
                    }))
                    logger.info(f"💓 Heartbeat #{self._cycles}")

            except Exception as e:
                logger.error(f"Error ciclo #{self._cycles}: {e}\n{traceback.format_exc()}")

            await asyncio.sleep(POLL_INTERVAL)


# ── Entry point ───────────────────────────────────────────────────

async def main() -> None:
    daemon = LevelBreakAlert()
    await daemon.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Detenido por usuario.")
    except Exception as e:
        logger.critical(f"Error fatal: {e}")
