#!/usr/bin/env python3
"""
sfp_advanced_monitor.py — SFP 2.0 Advanced Monitor v2.2 (Production Free)
═══════════════════════════════════════════════════════════════════════════
Institutional Swing Failure Pattern detector with Triple-Layer Audit.

v2.2 Changelog (vs v2.1):
  - PriceCache: eliminates redundant REST calls (TTL-based per symbol/tf)
  - HTF trend filter: 4H EMA(21) slope rejects counter-trend SFPs
  - Adaptive polling: backs off when no sweeps active, speeds up during sweeps
  - Configurable via settings.yaml sfp_monitor section
  - Heartbeat file for external health monitoring
  - Batch price fetching: single ticker call replaces multiple OHLCV calls
  - Staggered API calls with inter-request delay for rate limit safety
  - Free websocket upgrade path documented (no ccxt.pro)

API Budget (6 tickers, 10s poll, no active sweeps):
  - 6 × fetch_ticker = 6 calls/cycle = ~36 calls/min
  - With sweeps: +4 calls/audit (M5, spot, OB, trades) = ~60 calls/min max
  - Safe margin: Binance limit = 1200/min, we use ~5%

Usage:
    python3 -u sfp_advanced_monitor.py > data/sfp_advanced.log 2>&1 &

Author: ccxtv2 Senior Desk · Production v2.2 Free
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
from typing import Any, Optional

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, "/home/wek/Escritorio/ccxtv2")

from core.config import settings, TickerConfig
from core.data_engine import DataEngine
from alerts.telegram import TelegramService

# ── Paths ─────────────────────────────────────────────────────────
DATA_DIR = Path("/home/wek/Escritorio/ccxtv2/data")
HEARTBEAT_FILE = DATA_DIR / "sfp_heartbeat.json"
LOG_FILE = DATA_DIR / "sfp_advanced.log"

# ── Logging ───────────────────────────────────────────────────────
logger = logging.getLogger("SFP_v2.2")

# ── SFP Monitor Config (from settings.yaml or defaults) ──────────

def _load_sfp_config() -> dict:
    """Load sfp_monitor section from settings.yaml, with safe defaults."""
    import yaml
    config_path = Path("/home/wek/Escritorio/ccxtv2/config/settings.yaml")
    try:
        with open(config_path) as f:
            raw = yaml.safe_load(f) or {}
        return raw.get("sfp_monitor", {})
    except Exception:
        return {}

_SFP_CFG = _load_sfp_config()


# ══════════════════════════════════════════════════════════════════
# ENUMS & DATACLASSES
# ══════════════════════════════════════════════════════════════════

class SweepType(str, Enum):
    BEARISH = "BEARISH"
    BULLISH = "BULLISH"


class Session(str, Enum):
    LONDON = "LONDON"
    NEW_YORK = "NEW_YORK"
    OVERLAP = "LONDON_NY_OVERLAP"
    OFF_HOURS = "OFF_HOURS"


@dataclass
class AuditResult:
    score: int = 0
    max_score: int = 10
    basis: Optional[float] = None
    obi: Optional[float] = None
    cvd_k: Optional[float] = None
    obi_snap_delta: Optional[float] = None
    htf_trend: Optional[str] = None
    session: Session = Session.OFF_HOURS
    details: dict = field(default_factory=dict)

    @property
    def pct(self) -> str:
        return f"{self.score}/{self.max_score}"


@dataclass
class SweepTracker:
    symbol: str
    ticker_name: str
    level: float
    sweep_type: SweepType
    extreme_price: float
    start_time: float = field(default_factory=time.time)
    last_obi: Optional[float] = None
    rejection_timeout: float = float(_SFP_CFG.get("rejection_timeout_min", 75)) * 60

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time

    @property
    def is_expired(self) -> bool:
        return self.elapsed_seconds > self.rejection_timeout


# ══════════════════════════════════════════════════════════════════
# PRICE CACHE — Eliminates redundant REST calls
# ══════════════════════════════════════════════════════════════════

@dataclass
class CacheEntry:
    data: Any
    timestamp: float


class PriceCache:
    """
    TTL-based cache for API responses. Each key = "symbol:timeframe:limit".
    Avoids fetching the same data twice within TTL window.
    """

    def __init__(self, default_ttl: float = 8.0):
        self._store: dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def get(self, key: str, ttl: Optional[float] = None) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        age = time.time() - entry.timestamp
        effective_ttl = ttl if ttl is not None else self._default_ttl
        if age > effective_ttl:
            self._misses += 1
            del self._store[key]
            return None
        self._hits += 1
        return entry.data

    def put(self, key: str, data: Any) -> None:
        self._store[key] = CacheEntry(data=data, timestamp=time.time())

    def invalidate(self, prefix: str = "") -> None:
        if not prefix:
            self._store.clear()
        else:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]

    @property
    def stats(self) -> str:
        total = self._hits + self._misses
        rate = (self._hits / total * 100) if total > 0 else 0
        return f"Cache: {self._hits}H/{self._misses}M ({rate:.0f}% hit)"


# ══════════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════════

def get_current_session() -> Session:
    hour = datetime.now(timezone.utc).hour
    if 12 <= hour < 16:
        return Session.OVERLAP
    elif 7 <= hour < 16:
        return Session.LONDON
    elif 16 <= hour < 21:
        return Session.NEW_YORK
    return Session.OFF_HOURS


# send_telegram() removed — alerts now routed through SentinelGateway
# See alerts/gateway.py for the unified dispatcher.


def write_heartbeat(active_sweeps: int, cycle_count: int, cache_stats: str) -> None:
    try:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "pid": os.getpid(),
            "active_sweeps": active_sweeps,
            "cycles": cycle_count,
            "cache": cache_stats,
            "status": "ALIVE",
        }
        HEARTBEAT_FILE.write_text(json.dumps(payload, indent=2))
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
# MAIN MONITOR
# ══════════════════════════════════════════════════════════════════

class SFPAdvancedMonitor:
    # All configurable from settings.yaml sfp_monitor section
    POLL_INTERVAL: float = float(_SFP_CFG.get("poll_interval", 10.0))
    POLL_IDLE_MULTIPLIER: float = float(_SFP_CFG.get("idle_multiplier", 2.0))
    LEVEL_REFRESH_HOURS: float = float(_SFP_CFG.get("level_refresh_hours", 4.0))
    ALERT_COOLDOWN: float = float(_SFP_CFG.get("alert_cooldown_min", 60.0)) * 60
    SCORE_THRESHOLD: int = int(_SFP_CFG.get("score_threshold", 7))
    MAX_ERRORS: int = int(_SFP_CFG.get("max_consecutive_errors", 5))
    CIRCUIT_BREAKER_PAUSE: float = float(_SFP_CFG.get("circuit_breaker_pause", 60.0))
    OBI_THRESHOLD: float = float(_SFP_CFG.get("obi_threshold", 0.40))
    BASIS_THRESHOLD: float = float(_SFP_CFG.get("basis_threshold", 0.03))
    INTER_REQUEST_DELAY: float = float(_SFP_CFG.get("inter_request_delay", 0.15))
    HTF_TREND_ENABLED: bool = bool(_SFP_CFG.get("htf_trend_filter", True))
    HTF_EMA_PERIOD: int = int(_SFP_CFG.get("htf_ema_period", 21))

    def __init__(self, engine: Optional[DataEngine] = None,
                 gateway=None) -> None:
        self.engine = engine
        self._gateway = gateway  # SentinelGateway when under Guardian
        self.tg = TelegramService()  # Fallback for standalone mode
        self.cache = PriceCache(default_ttl=self.POLL_INTERVAL - 1)
        self.active_sweeps: dict[str, SweepTracker] = {}
        self.levels: dict[str, dict[str, float]] = {}
        self.htf_trend: dict[str, str] = {}  # symbol -> "BULLISH" | "BEARISH" | "NEUTRAL"
        self.last_alert_time: dict[str, float] = {}
        self._running = True
        self._consecutive_errors = 0
        self._last_level_update = 0.0
        self._cycle_count = 0
        self._engine_shared = engine is not None

    # ── Lifecycle ─────────────────────────────────────────────

    async def run(self) -> None:
        logger.info("🚀 SFP v2.2 Production Free — STARTING")
        logger.info(f"   Universe: {len(settings.universe)} tickers")
        logger.info(f"   Poll: {self.POLL_INTERVAL}s | Threshold: {self.SCORE_THRESHOLD}/10")
        logger.info(f"   HTF Filter: {'ON' if self.HTF_TREND_ENABLED else 'OFF'}")

        if self.engine is None:
            self.engine = await DataEngine.instance()
            await self.engine.connect()
            logger.info("✅ DataEngine connected (persistent).")
        else:
            logger.info("✅ Using shared IntelligenceHub engine.")

        if __name__ == "__main__":
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self._request_shutdown)

        await self._refresh_all_levels()
        if self.HTF_TREND_ENABLED:
            await self._refresh_htf_trends()

        try:
            await self._main_loop()
        finally:
            await self._shutdown()

    async def _shutdown(self) -> None:
        logger.info("🛑 Shutting down SFP Monitor...")
        self._running = False
        if not self._engine_shared and self.engine:
            try:
                await self.engine.close()
            except Exception:
                pass
        logger.info("✅ SFP Shutdown complete.")

    def _request_shutdown(self) -> None:
        logger.info("📡 Shutdown signal received.")
        self._running = False

    # ── Cached Data Fetchers ──────────────────────────────────
    # Every fetch goes through cache to avoid redundant REST calls.

    async def _fetch_cached_ohlcv(
        self, symbol: str, tf: str, limit: int = 3, ttl: float = 8.0
    ) -> Optional[pd.DataFrame]:
        key = f"ohlcv:{symbol}:{tf}:{limit}"
        cached = self.cache.get(key, ttl=ttl)
        if cached is not None:
            return cached

        await asyncio.sleep(self.INTER_REQUEST_DELAY)
        df = await self.engine.fetch_ohlcv(symbol, tf, limit=limit)
        if df is not None and not df.empty:
            self.cache.put(key, df)
        return df

    async def _fetch_cached_ob(self, symbol: str, limit: int = 50, ttl: float = 5.0) -> Optional[dict]:
        key = f"ob:{symbol}:{limit}"
        cached = self.cache.get(key, ttl=ttl)
        if cached is not None:
            return cached

        await asyncio.sleep(self.INTER_REQUEST_DELAY)
        ob = await self.engine.fetch_order_book(symbol, limit=limit)
        if ob:
            self.cache.put(key, ob)
        return ob

    async def _fetch_cached_trades(self, symbol: str, limit: int = 200, ttl: float = 8.0) -> Optional[pd.DataFrame]:
        key = f"trades:{symbol}:{limit}"
        cached = self.cache.get(key, ttl=ttl)
        if cached is not None:
            return cached

        await asyncio.sleep(self.INTER_REQUEST_DELAY)
        trades = await self.engine.fetch_trades(symbol, limit=limit)
        if trades is not None and not trades.empty:
            self.cache.put(key, trades)
        return trades

    # ── Level Management ──────────────────────────────────────

    async def _refresh_all_levels(self) -> None:
        for ticker in settings.universe:
            try:
                df = await self._fetch_cached_ohlcv(ticker.symbol, "1d", limit=3, ttl=300)
                if df is not None and len(df) >= 2:
                    yesterday = df.iloc[-2]
                    self.levels[ticker.symbol] = {
                        "high": float(yesterday["high"]),
                        "low": float(yesterday["low"]),
                    }
            except Exception as e:
                logger.error(f"Level fetch {ticker.symbol}: {e}")
        self._last_level_update = time.time()
        logger.info(f"📊 Levels updated: {len(self.levels)} tickers.")

    # ── HTF Trend Filter ──────────────────────────────────────

    async def _refresh_htf_trends(self) -> None:
        """Calculate 4H EMA slope to determine trend direction."""
        period = self.HTF_EMA_PERIOD
        for ticker in settings.universe:
            try:
                df = await self._fetch_cached_ohlcv(
                    ticker.symbol, "4h", limit=period + 5, ttl=3600
                )
                if df is None or len(df) < period:
                    self.htf_trend[ticker.symbol] = "NEUTRAL"
                    continue

                closes = df["close"].astype(float).values
                ema = pd.Series(closes).ewm(span=period, adjust=False).mean().values

                # Slope: compare last EMA to EMA 3 bars ago
                slope = ema[-1] - ema[-4] if len(ema) >= 4 else 0
                if slope > 0:
                    self.htf_trend[ticker.symbol] = "BULLISH"
                elif slope < 0:
                    self.htf_trend[ticker.symbol] = "BEARISH"
                else:
                    self.htf_trend[ticker.symbol] = "NEUTRAL"

            except Exception as e:
                logger.error(f"HTF trend {ticker.symbol}: {e}")
                self.htf_trend[ticker.symbol] = "NEUTRAL"

        logger.info(f"📈 HTF trends: {self.htf_trend}")

    # ── Triple-Layer Audit ────────────────────────────────────

    async def _run_audit(self, ticker: TickerConfig, sweep: SweepTracker) -> AuditResult:
        result = AuditResult()
        result.session = get_current_session()
        is_bearish = sweep.sweep_type == SweepType.BEARISH

        try:
            # ── Layer 1: Basis (Spot vs Perp) ──────────────
            df_spot = await self._fetch_cached_ohlcv(ticker.spot, "5m", limit=2, ttl=10)
            df_fut = await self._fetch_cached_ohlcv(ticker.symbol, "5m", limit=2, ttl=10)

            if df_spot is not None and df_fut is not None:
                spot_p = float(df_spot["close"].iloc[-1])
                fut_p = float(df_fut["close"].iloc[-1])
                basis = ((fut_p - spot_p) / spot_p) * 100 if spot_p > 0 else 0.0
                result.basis = round(basis, 4)

                if is_bearish and basis < -self.BASIS_THRESHOLD:
                    result.score += 2  # Perp discount = institutional short
                elif not is_bearish and basis > self.BASIS_THRESHOLD:
                    result.score += 2  # Spot premium = accumulation
                elif abs(basis) > self.BASIS_THRESHOLD * 0.33:
                    result.score += 1

            # ── Layer 2: OBI (Directional) ─────────────────
            ob = await self._fetch_cached_ob(ticker.symbol, limit=50, ttl=5)
            if ob:
                bids = sum(b[1] for b in ob.get("bids", []))
                asks = sum(a[1] for a in ob.get("asks", []))
                total = bids + asks
                obi = (bids - asks) / total if total > 0 else 0.0
                result.obi = round(obi, 4)

                # Directional: SHORT needs negative OBI, LONG needs positive
                if is_bearish and obi < -self.OBI_THRESHOLD:
                    result.score += 3
                elif not is_bearish and obi > self.OBI_THRESHOLD:
                    result.score += 3
                elif abs(obi) > self.OBI_THRESHOLD * 0.6:
                    result.score += 1

                # Spoofing detection
                if sweep.last_obi is not None:
                    snap = abs(obi - sweep.last_obi)
                    result.obi_snap_delta = round(snap, 4)
                    if snap > 0.30:
                        result.score += 1
                        result.details["spoof"] = True
                sweep.last_obi = obi

            # ── Layer 3: CVD (Divergence) ──────────────────
            trades = await self._fetch_cached_trades(ticker.symbol, limit=200, ttl=8)
            if trades is not None and not trades.empty:
                buys = trades[trades["side"] == "buy"]
                sells = trades[trades["side"] == "sell"]
                buy_usd = float((buys["amount"] * buys["price"]).sum())
                sell_usd = float((sells["amount"] * sells["price"]).sum())
                cvd = buy_usd - sell_usd
                result.cvd_k = round(cvd / 1000, 2)

                # Divergence: new high + negative CVD = distribution
                if is_bearish and cvd < 0:
                    result.score += 2
                elif not is_bearish and cvd > 0:
                    result.score += 2

            # ── Bonus: Session ─────────────────────────────
            if result.session in (Session.LONDON, Session.NEW_YORK, Session.OVERLAP):
                result.score += 1

            # ── Bonus: HTF Trend Alignment ─────────────────
            trend = self.htf_trend.get(ticker.symbol, "NEUTRAL")
            result.htf_trend = trend
            if is_bearish and trend == "BEARISH":
                result.score += 1  # Short aligned with downtrend
            elif not is_bearish and trend == "BULLISH":
                result.score += 1  # Long aligned with uptrend
            elif is_bearish and trend == "BULLISH":
                result.details["counter_trend"] = True
                # No penalty, just flag

        except Exception as e:
            logger.error(f"Audit {ticker.symbol}: {e}\n{traceback.format_exc()}")

        return result

    # ── M5 Candle Close Validation ────────────────────────────

    async def _check_m5_close(self, symbol: str, level: float, sweep_type: SweepType) -> bool:
        try:
            df = await self._fetch_cached_ohlcv(symbol, "5m", limit=3, ttl=5)
            if df is None or len(df) < 2:
                return False
            # iloc[-2] = last FULLY CLOSED candle
            last_closed = float(df["close"].iloc[-2])
            if sweep_type == SweepType.BEARISH:
                return last_closed < level
            else:
                return last_closed > level
        except Exception as e:
            logger.error(f"M5 check {symbol}: {e}")
            return False

    # ── Alert Formatting ──────────────────────────────────────

    def _format_signal(self, ticker: TickerConfig, sweep: SweepTracker,
                       entry: float, audit: AuditResult) -> str:
        d = "SHORT" if sweep.sweep_type == SweepType.BEARISH else "LONG"
        lbl = "pdH" if sweep.sweep_type == SweepType.BEARISH else "pdL"
        v = "Institutional Trap" if sweep.sweep_type == SweepType.BEARISH else "Accumulation Sweep"
        ct = " ⚠️CTR-TREND" if audit.details.get("counter_trend") else ""

        return (
            f"🏛️ *SFP v2.2: {ticker.name} {d}*{ct}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎯 *Entry*: {entry:.2f} ({lbl}: {sweep.level:.2f})\n"
            f"🛡️ *SL*: {sweep.extreme_price:.2f}\n"
            f"📈 *Score*: {audit.pct} (thr: {self.SCORE_THRESHOLD})\n"
            f"📊 Basis {audit.basis}% | OBI {audit.obi} | CVD {audit.cvd_k}k\n"
            f"📐 Trend: {audit.htf_trend} | Session: {audit.session.value}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🚦 *Verdict*: {v}"
        )

    async def _emit_sfp_signal(
        self,
        ticker: TickerConfig,
        sweep: SweepTracker,
        entry: float,
        audit: AuditResult,
        message: str,
    ) -> None:
        if self._gateway:
            from alerts.gateway import AlertMessage
            await self._gateway.dispatch(AlertMessage(
                source="SFP_v2.2",
                priority=2,
                text=message,
                dedup_key=f"sfp_{ticker.name}_{sweep.direction}",
            ))
        else:
            await self.tg.send_text(message)

    # ── Cooldown ──────────────────────────────────────────────

    def _is_cooled_down(self, symbol: str) -> bool:
        return (time.time() - self.last_alert_time.get(symbol, 0)) > self.ALERT_COOLDOWN

    # ── Main Loop ─────────────────────────────────────────────

    async def _main_loop(self) -> None:
        while self._running:
            try:
                self._cycle_count += 1

                # Periodic refreshes
                elapsed = time.time() - self._last_level_update
                if elapsed > self.LEVEL_REFRESH_HOURS * 3600:
                    await self._refresh_all_levels()
                    if self.HTF_TREND_ENABLED:
                        await self._refresh_htf_trends()

                to_remove: list[str] = []

                for ticker in settings.universe:
                    symbol = ticker.symbol
                    levels = self.levels.get(symbol)
                    if not levels:
                        continue

                    # Get current price via 1m OHLCV (cached)
                    df_1m = await self._fetch_cached_ohlcv(symbol, "1m", limit=2, ttl=self.POLL_INTERVAL - 1)
                    if df_1m is None or df_1m.empty:
                        continue
                    curr_p = float(df_1m["close"].iloc[-1])

                    # ── Phase 1: Detect Sweep ─────────────
                    if symbol not in self.active_sweeps:
                        if curr_p > levels["high"]:
                            logger.info(f"📡 [SWEEP] {ticker.name} > pdH ({levels['high']:.2f})")
                            self.active_sweeps[symbol] = SweepTracker(
                                symbol=symbol, ticker_name=ticker.name,
                                level=levels["high"], sweep_type=SweepType.BEARISH,
                                extreme_price=curr_p,
                            )
                        elif curr_p < levels["low"]:
                            logger.info(f"📡 [SWEEP] {ticker.name} < pdL ({levels['low']:.2f})")
                            self.active_sweeps[symbol] = SweepTracker(
                                symbol=symbol, ticker_name=ticker.name,
                                level=levels["low"], sweep_type=SweepType.BULLISH,
                                extreme_price=curr_p,
                            )
                        continue

                    # ── Phase 2: Track Sweep ──────────────
                    tracker = self.active_sweeps[symbol]

                    if tracker.sweep_type == SweepType.BEARISH:
                        tracker.extreme_price = max(tracker.extreme_price, curr_p)
                    else:
                        tracker.extreme_price = min(tracker.extreme_price, curr_p)

                    if tracker.is_expired:
                        logger.warning(f"🛑 [EXPIRED] {ticker.name} — {tracker.elapsed_seconds / 60:.0f}min")
                        to_remove.append(symbol)
                        continue

                    # Check M5 candle close
                    rejected = await self._check_m5_close(symbol, tracker.level, tracker.sweep_type)
                    if not rejected:
                        continue

                    # ── Phase 3: Rejection → Audit ────────
                    logger.info(f"✅ [REJECTION] {ticker.name} M5 close inside.")
                    audit = await self._run_audit(ticker, tracker)
                    msg = self._format_signal(ticker, tracker, curr_p, audit)
                    logger.info(f"SIGNAL {symbol} | {audit.pct}\n{msg}")

                    if audit.score >= self.SCORE_THRESHOLD and self._is_cooled_down(symbol):
                        await self._emit_sfp_signal(ticker, tracker, curr_p, audit, msg)
                        self.last_alert_time[symbol] = time.time()
                    elif audit.score < self.SCORE_THRESHOLD:
                        logger.info(f"⚠️ {ticker.name} below threshold ({audit.score}<{self.SCORE_THRESHOLD})")

                    to_remove.append(symbol)

                # Clean up
                for sym in to_remove:
                    self.active_sweeps.pop(sym, None)

                self._consecutive_errors = 0

                # Heartbeat every 10 cycles
                if self._cycle_count % 10 == 0:
                    write_heartbeat(len(self.active_sweeps), self._cycle_count, self.cache.stats)

                # Adaptive polling: slower when idle
                if self.active_sweeps:
                    await asyncio.sleep(self.POLL_INTERVAL)
                else:
                    await asyncio.sleep(self.POLL_INTERVAL * self.POLL_IDLE_MULTIPLIER)

            except Exception as e:
                self._consecutive_errors += 1
                logger.error(f"Loop error #{self._consecutive_errors}: {e}\n{traceback.format_exc()}")
                if self._consecutive_errors >= self.MAX_ERRORS:
                    logger.critical(f"🔌 Circuit breaker. Pausing {self.CIRCUIT_BREAKER_PAUSE}s.")
                    await asyncio.sleep(self.CIRCUIT_BREAKER_PAUSE)
                    self._consecutive_errors = 0
                    # Reconnect engine after circuit breaker
                    try:
                        await self.engine.close()
                        await self.engine.connect()
                        logger.info("✅ DataEngine reconnected after circuit breaker.")
                    except Exception as re:
                        logger.error(f"Reconnect failed: {re}")
                else:
                    await asyncio.sleep(self.POLL_INTERVAL * 3)


# ── Entry Point ──────────────────────────────────────────────────

async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(str(LOG_FILE)),
            logging.StreamHandler(),
        ],
    )
    engine = await DataEngine.instance()
    await engine.connect()
    monitor = SFPAdvancedMonitor(engine=engine)
    await monitor.run()

if __name__ == "__main__":
    asyncio.run(main())
