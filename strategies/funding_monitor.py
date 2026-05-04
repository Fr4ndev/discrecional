#!/usr/bin/env python3
"""
strategies/funding_monitor.py — Multi-Exchange Funding + OI + OBI Monitor
═════════════════════════════════════════════════════════════════════════════
Real-time async monitor for BTCUSDT & ETHUSDT perpetual futures.

Tracks three microstructure variables across Binance, Bybit, OKX, Hyperliquid:
  • Funding Rate (actual + ΔFunding 1h)
  • Open Interest (actual + ΔOI 30m / 1h)
  • Order Book Imbalance (OBI top-50 levels)

On confluence trigger → fires ZScore + SpotDiff + Heatmap analysis
and generates a dossier in ./reports/.

Scientific basis: He [1], Ackerer [2], Joshi [3], Zhang [4],
                  Zhivkov [5], Giagkiozis [6], Bieganowski [7].
"""

import asyncio
import json
import logging
import os
import sys
import time
from collections import deque
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

import numpy as np

# ── Ensure ccxtv2 root is importable ─────────────────────────────
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

import ccxt.async_support as ccxt

from strategies.funding_monitor_config import (
    FundingMonitorConfig,
    load_monitor_config,
)

logger = logging.getLogger("FundingMonitor")


# ══════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════

class ExchangeSnapshot:
    """Single polling snapshot for one exchange + one asset."""
    __slots__ = (
        "exchange", "asset", "timestamp",
        "funding_rate", "open_interest", "obi",
        "bid_volume", "ask_volume",
    )

    def __init__(
        self,
        exchange: str,
        asset: str,
        timestamp: float,
        funding_rate: Optional[float] = None,
        open_interest: Optional[float] = None,
        obi: Optional[float] = None,
        bid_volume: float = 0.0,
        ask_volume: float = 0.0,
    ):
        self.exchange = exchange
        self.asset = asset
        self.timestamp = timestamp
        self.funding_rate = funding_rate
        self.open_interest = open_interest
        self.obi = obi
        self.bid_volume = bid_volume
        self.ask_volume = ask_volume

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange": self.exchange,
            "asset": self.asset,
            "timestamp": self.timestamp,
            "funding_rate": self.funding_rate,
            "open_interest": self.open_interest,
            "obi": self.obi,
            "bid_volume": self.bid_volume,
            "ask_volume": self.ask_volume,
        }


class IndicatorState:
    """Aggregated indicator state for one asset across all exchanges."""
    __slots__ = (
        "asset", "timestamp",
        "funding_rates", "delta_funding_1h",
        "open_interests", "delta_oi_30m", "delta_oi_1h",
        "obis",
        "trigger_scalp", "trigger_swing",
    )

    def __init__(self, asset: str):
        self.asset = asset
        self.timestamp: float = 0.0
        # Per-exchange current values
        self.funding_rates: Dict[str, Optional[float]] = {}
        self.delta_funding_1h: Dict[str, Optional[float]] = {}
        self.open_interests: Dict[str, Optional[float]] = {}
        self.delta_oi_30m: Dict[str, Optional[float]] = {}
        self.delta_oi_1h: Dict[str, Optional[float]] = {}
        self.obis: Dict[str, Optional[float]] = {}
        # Trigger flags
        self.trigger_scalp: bool = False
        self.trigger_swing: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset": self.asset,
            "timestamp": self.timestamp,
            "timestamp_iso": datetime.fromtimestamp(
                self.timestamp, tz=timezone.utc
            ).isoformat() if self.timestamp else None,
            "funding_rates": self.funding_rates,
            "delta_funding_1h": self.delta_funding_1h,
            "open_interests": self.open_interests,
            "delta_oi_30m": self.delta_oi_30m,
            "delta_oi_1h": self.delta_oi_1h,
            "obis": self.obis,
            "trigger_scalp": self.trigger_scalp,
            "trigger_swing": self.trigger_swing,
        }


# ══════════════════════════════════════════════════════════════════
# TRIGGER ENGINE
# ══════════════════════════════════════════════════════════════════

def evaluate_triggers(
    state: IndicatorState,
    cfg: FundingMonitorConfig,
) -> Tuple[bool, bool, Dict[str, Any]]:
    """
    Evaluate confluence triggers for an asset.

    Returns:
        (scalp_triggered, swing_triggered, details_dict)

    Scalp (High Freq): OBI > 0.45 OR (ΔFunding > 0.005% AND |Funding| > 0.01%)
    Swing (Low Freq): ΔOI > 10% AND |Z-Score (trend)| > 2 (implied by high absolute funding and OI trend)
    """
    th = cfg.thresholds

    # Aggregate: take the max absolute value across exchanges
    max_funding_abs = _max_abs(state.funding_rates)
    max_delta_funding = _max_abs(state.delta_funding_1h)
    max_delta_oi_1h = _max_abs(state.delta_oi_1h)
    max_delta_oi_30m = _max_abs(state.delta_oi_30m)
    max_obi_abs = _max_abs(state.obis)

    details = {
        "max_funding_abs": max_funding_abs,
        "max_delta_funding_1h": max_delta_funding,
        "max_delta_oi_1h": max_delta_oi_1h,
        "max_delta_oi_30m": max_delta_oi_30m,
        "max_obi_abs": max_obi_abs,
    }

    # ── Scalp rule (Live OBI & Spikes) ───────────────────────────
    cond_obi_scalp = (max_obi_abs is not None and max_obi_abs > 0.45)
    cond_funding_spike = (
        (max_delta_funding is not None and max_delta_funding > th.delta_funding_1h)
        and (max_funding_abs is not None and max_funding_abs > th.conservative_funding_abs)
    )
    scalp = cond_obi_scalp or cond_funding_spike

    # ── Swing rule (Context / Trend / Accumulation) ──────────────
    swing = (
        (max_delta_oi_1h is not None and max_delta_oi_1h > 10.0)
        and (max_funding_abs is not None and max_funding_abs > th.conservative_funding_abs)
    )

    return scalp, swing, details


def _max_abs(d: Dict[str, Optional[float]]) -> Optional[float]:
    """Return max absolute value from a dict of nullable floats."""
    vals = [abs(v) for v in d.values() if v is not None]
    return max(vals) if vals else None


# ══════════════════════════════════════════════════════════════════
# DOSSIER GENERATOR
# ══════════════════════════════════════════════════════════════════

def generate_dossier(
    state: IndicatorState,
    trigger_mode: str,
    details: Dict[str, Any],
    cfg: FundingMonitorConfig,
) -> Tuple[str, str]:
    """
    Generate a decision dossier in JSON and Markdown.

    Returns:
        (json_path, md_path) — absolute paths to saved files.
    """
    reports_dir = Path(cfg.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc)
    ts_slug = ts.strftime("%Y%m%d_%H%M%S")
    base_name = f"dossier_{state.asset}_{ts_slug}"

    # ── Determine trade recommendation ───────────────────────────
    max_funding = _max_abs(state.funding_rates)
    max_obi = _max_abs(state.obis)

    # Infer direction from funding sign (negative → market is short-heavy)
    any_funding_vals = [v for v in state.funding_rates.values() if v is not None]
    avg_funding = (
        sum(any_funding_vals) / len(any_funding_vals)
        if any_funding_vals else 0.0
    )

    if avg_funding > 0:
        direction = "SHORT_BIAS"
        trade_type = "Contrarian Short / Scalp (funding longs paying)"
    elif avg_funding < 0:
        direction = "LONG_BIAS"
        trade_type = "Contrarian Long / Scalp (funding shorts paying)"
    else:
        direction = "NEUTRAL"
        trade_type = "Wait for clearer signal"

    # Upgrade to swing if ΔOI is very large
    max_doi = details.get("max_delta_oi_1h")
    if max_doi and max_doi > 15.0:
        trade_type = f"Swing / Position ({direction}) — ΔOI {max_doi:.1f}% indicates heavy positioning"

    dossier_data = {
        "timestamp": ts.isoformat(),
        "asset": state.asset,
        "trigger_mode": trigger_mode,
        "indicators": state.to_dict(),
        "confluence_details": details,
        "direction": direction,
        "trade_recommendation": trade_type,
        "scripts_triggered": ["zscore.py", "spotdiff.py", "heatmap.py"],
        "reports_path": str(reports_dir.resolve()),
    }

    # ── Save JSON ────────────────────────────────────────────────
    json_path = reports_dir / f"{base_name}.json"
    with open(json_path, "w") as f:
        json.dump(dossier_data, f, indent=2, default=str)

    # ── Save Markdown ────────────────────────────────────────────
    md_lines = [
        f"# 📊 Dossier de Decisión — {state.asset}",
        f"**Timestamp:** {ts.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"**Trigger Mode:** `{trigger_mode}`",
        "",
        "---",
        "",
        "## Indicadores Actuales",
        "",
        "| Exchange | Funding (%) | ΔFunding 1h (%) | OI | ΔOI 1h (%) | OBI |",
        "|----------|-------------|-----------------|-----|------------|-----|",
    ]

    for ex in cfg.exchanges:
        fr = state.funding_rates.get(ex)
        dfr = state.delta_funding_1h.get(ex)
        oi = state.open_interests.get(ex)
        doi = state.delta_oi_1h.get(ex)
        obi = state.obis.get(ex)

        md_lines.append(
            f"| {ex} "
            f"| {fr:.6f} " if fr is not None else f"| {ex} | — "
            f"| {dfr:.6f} " if dfr is not None else "| — "
            f"| {oi:,.0f} " if oi is not None else "| — "
            f"| {doi:.2f} " if doi is not None else "| — "
            f"| {obi:+.4f} |" if obi is not None else "| — |"
        )

    md_lines.extend([
        "",
        "---",
        "",
        "## Confluencia Detectada",
        "",
        f"- **Max |Funding|:** {details.get('max_funding_abs', '—')}",
        f"- **Max ΔFunding 1h:** {details.get('max_delta_funding_1h', '—')}",
        f"- **Max ΔOI 1h:** {details.get('max_delta_oi_1h', '—')}%",
        f"- **Max |OBI|:** {details.get('max_obi_abs', '—')}",
        "",
        "---",
        "",
        "## Recomendación",
        "",
        f"🎯 **Dirección:** {direction}",
        f"📋 **Tipo de Trade:** {trade_type}",
        "",
        "---",
        "",
        "## Scripts Ejecutados",
        "",
        "- ✅ `zscore.py` — MVRV Z-Score con OI, CVD, Wyckoff",
        "- ✅ `spotdiff.py` — Spot-Futures Diff + Kelly Sizing",
        "- ✅ `heatmap.py` — S/R Heatmap + Volume Profile",
        "",
        f"📁 Outputs en: `{reports_dir.resolve()}/`",
    ])

    md_path = reports_dir / f"{base_name}.md"
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines))

    logger.info(f"📝 Dossier saved: {json_path.name} + {md_path.name}")
    return str(json_path), str(md_path)


# ══════════════════════════════════════════════════════════════════
# MAIN MONITOR ENGINE
# ══════════════════════════════════════════════════════════════════

class FundingMonitorEngine:
    """
    Async multi-exchange Funding + OI + OBI monitor.

    Usage:
        engine = FundingMonitorEngine()
        await engine.start()   # runs polling loop
        await engine.stop()    # graceful shutdown
    """

    def __init__(self, config: Optional[FundingMonitorConfig] = None):
        self.cfg = config or load_monitor_config()
        self._exchanges: Dict[str, ccxt.Exchange] = {}
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None

        # Rolling history: {(exchange, asset): deque of ExchangeSnapshot}
        self._history: Dict[Tuple[str, str], Deque[ExchangeSnapshot]] = {}

        # Current aggregated state per asset
        self._states: Dict[str, IndicatorState] = {
            asset: IndicatorState(asset) for asset in self.cfg.assets
        }

        # Last dossier paths
        self._last_dossier: Optional[Dict[str, str]] = None

        # Trigger cooldown (avoid spamming analysis)
        self._last_trigger_ts: Dict[str, float] = {}
        self._trigger_cooldown_seconds: float = 300.0  # 5 min

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_states(self) -> Dict[str, Dict]:
        return {
            asset: state.to_dict()
            for asset, state in self._states.items()
        }

    @property
    def last_dossier(self) -> Optional[Dict[str, str]]:
        return self._last_dossier

    # ── Exchange Lifecycle ────────────────────────────────────────

    async def _init_exchanges(self) -> None:
        """Create one CCXT async instance per configured exchange."""
        for ex_id in self.cfg.exchanges:
            try:
                exchange_cls = getattr(ccxt, ex_id)
                exchange = exchange_cls({
                    "enableRateLimit": True,
                    "timeout": 30000,
                    "options": {"defaultType": "swap"},
                })
                await exchange.load_markets()
                self._exchanges[ex_id] = exchange
                logger.info(f"✅ Connected to {ex_id} ({len(exchange.markets)} markets)")
            except Exception as e:
                logger.error(f"❌ Failed to connect to {ex_id}: {e}")

        if not self._exchanges:
            raise RuntimeError("No exchanges connected — cannot start monitor")

    async def _close_exchanges(self) -> None:
        """Close all exchange connections."""
        for ex_id, exchange in self._exchanges.items():
            try:
                await exchange.close()
                logger.info(f"Closed {ex_id}")
            except Exception:
                pass
        self._exchanges.clear()

    # ── Data Fetchers ─────────────────────────────────────────────

    async def _fetch_funding_rate(
        self, exchange: ccxt.Exchange, ex_id: str, symbol: str
    ) -> Optional[float]:
        """Fetch current funding rate for a symbol. Returns rate as %."""
        try:
            result = await exchange.fetch_funding_rate(symbol)
            rate = result.get("fundingRate")
            if rate is not None:
                return float(rate) * 100.0  # Convert to %
            return None
        except ccxt.BadSymbol:
            logger.debug(f"{ex_id}: symbol {symbol} not found")
            return None
        except (ccxt.NetworkError, ccxt.ExchangeNotAvailable) as e:
            logger.warning(f"{ex_id} funding rate error for {symbol}: {e}")
            return None
        except Exception as e:
            logger.warning(f"{ex_id} unexpected funding error for {symbol}: {e}")
            return None

    async def _fetch_open_interest(
        self, exchange: ccxt.Exchange, ex_id: str, symbol: str
    ) -> Optional[float]:
        """Fetch open interest in base currency units."""
        try:
            result = await exchange.fetch_open_interest(symbol)
            oi = result.get("openInterestAmount") or result.get("openInterest")
            if oi is not None:
                return float(oi)
            return None
        except ccxt.BadSymbol:
            logger.debug(f"{ex_id}: OI symbol {symbol} not found")
            return None
        except (ccxt.NetworkError, ccxt.ExchangeNotAvailable) as e:
            logger.warning(f"{ex_id} OI error for {symbol}: {e}")
            return None
        except Exception as e:
            # Some exchanges may not support fetchOpenInterest
            logger.debug(f"{ex_id} OI not available for {symbol}: {e}")
            return None

    async def _fetch_obi(
        self, exchange: ccxt.Exchange, ex_id: str, symbol: str,
        depth: int = 50,
    ) -> Tuple[Optional[float], float, float]:
        """
        Fetch order book and compute OBI.

        OBI = (Σ bid_volume - Σ ask_volume) / (Σ bid_volume + Σ ask_volume)

        Returns:
            (obi, total_bid_volume, total_ask_volume)
        """
        try:
            ob = await exchange.fetch_order_book(symbol, limit=depth)
            bids = ob.get("bids", [])
            asks = ob.get("asks", [])

            if not bids or not asks:
                return None, 0.0, 0.0

            # Vectorized calculation with numpy
            bid_vols = np.array([b[1] for b in bids[:depth]], dtype=np.float64)
            ask_vols = np.array([a[1] for a in asks[:depth]], dtype=np.float64)

            total_bid = float(bid_vols.sum())
            total_ask = float(ask_vols.sum())
            total = total_bid + total_ask

            if total < 1e-12:
                return 0.0, total_bid, total_ask

            obi = (total_bid - total_ask) / total
            return obi, total_bid, total_ask

        except ccxt.BadSymbol:
            logger.debug(f"{ex_id}: OB symbol {symbol} not found")
            return None, 0.0, 0.0
        except Exception as e:
            logger.warning(f"{ex_id} order book error for {symbol}: {e}")
            return None, 0.0, 0.0

    # ── Single Exchange + Asset Poll ──────────────────────────────

    async def _poll_exchange_asset(
        self, ex_id: str, asset: str,
    ) -> Optional[ExchangeSnapshot]:
        """Poll one exchange for one asset. Returns snapshot or None."""
        exchange = self._exchanges.get(ex_id)
        if exchange is None:
            return None

        symbols = self.cfg.exchange_symbols.get(ex_id, {})
        symbol = symbols.get(asset)
        if not symbol:
            return None

        now = time.time()

        # Fetch all three data points concurrently for this exchange+asset
        funding_task = self._fetch_funding_rate(exchange, ex_id, symbol)
        oi_task = self._fetch_open_interest(exchange, ex_id, symbol)
        obi_task = self._fetch_obi(exchange, ex_id, symbol, self.cfg.orderbook_depth)

        funding, oi, (obi, bid_vol, ask_vol) = await asyncio.gather(
            funding_task, oi_task, obi_task
        )

        snap = ExchangeSnapshot(
            exchange=ex_id,
            asset=asset,
            timestamp=now,
            funding_rate=funding,
            open_interest=oi,
            obi=obi,
            bid_volume=bid_vol,
            ask_volume=ask_vol,
        )

        # Store in rolling history
        key = (ex_id, asset)
        if key not in self._history:
            self._history[key] = deque(maxlen=self.cfg.rolling_window_1h)
        self._history[key].append(snap)

        return snap

    # ── Delta Calculation ─────────────────────────────────────────

    def _compute_delta_funding_1h(
        self, ex_id: str, asset: str, current: Optional[float],
    ) -> Optional[float]:
        """ΔFunding = current - value ~1h ago."""
        if current is None:
            return None
        key = (ex_id, asset)
        hist = self._history.get(key)
        if not hist or len(hist) < 2:
            return None

        # Find sample closest to 1h ago
        target_idx = max(0, len(hist) - self.cfg.rolling_window_1h)
        old_snap = hist[target_idx]
        if old_snap.funding_rate is None:
            return None

        return current - old_snap.funding_rate

    def _compute_delta_oi(
        self, ex_id: str, asset: str, current: Optional[float],
        window: int,
    ) -> Optional[float]:
        """ΔOI (%) = ((current - old) / old) * 100."""
        if current is None or current < 1e-12:
            return None
        key = (ex_id, asset)
        hist = self._history.get(key)
        if not hist or len(hist) < 2:
            return None

        target_idx = max(0, len(hist) - window)
        old_snap = hist[target_idx]
        if old_snap.open_interest is None or old_snap.open_interest < 1e-12:
            return None

        return ((current - old_snap.open_interest) / old_snap.open_interest) * 100.0

    # ── Full Polling Cycle ────────────────────────────────────────

    async def _poll_cycle(self) -> None:
        """Execute one full polling cycle across all exchanges and assets."""
        # Gather all tasks
        tasks = []
        task_keys = []
        for ex_id in list(self._exchanges.keys()):
            for asset in self.cfg.assets:
                tasks.append(self._poll_exchange_asset(ex_id, asset))
                task_keys.append((ex_id, asset))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and update states
        for (ex_id, asset), result in zip(task_keys, results):
            if isinstance(result, Exception):
                logger.warning(f"Poll error {ex_id}/{asset}: {result}")
                continue
            if result is None:
                continue

            snap: ExchangeSnapshot = result
            state = self._states[asset]
            state.timestamp = snap.timestamp

            # Update current values
            state.funding_rates[ex_id] = snap.funding_rate
            state.open_interests[ex_id] = snap.open_interest
            state.obis[ex_id] = snap.obi

            # Compute deltas
            state.delta_funding_1h[ex_id] = self._compute_delta_funding_1h(
                ex_id, asset, snap.funding_rate
            )
            state.delta_oi_1h[ex_id] = self._compute_delta_oi(
                ex_id, asset, snap.open_interest, self.cfg.rolling_window_1h
            )
            state.delta_oi_30m[ex_id] = self._compute_delta_oi(
                ex_id, asset, snap.open_interest, self.cfg.rolling_window_30m
            )

        # Evaluate triggers for each asset
        for asset in self.cfg.assets:
            state = self._states[asset]
            scalp, swing, details = evaluate_triggers(state, self.cfg)
            state.trigger_scalp = scalp
            state.trigger_swing = swing

            # Check if we should fire
            should_trigger = (
                (self.cfg.trigger_mode in ("scalp", "any") and scalp)
                or (self.cfg.trigger_mode in ("swing", "any") and swing)
            )

            if should_trigger:
                # Cooldown check
                last_ts = self._last_trigger_ts.get(asset, 0.0)
                if time.time() - last_ts < self._trigger_cooldown_seconds:
                    logger.info(
                        f"⏳ {asset} trigger suppressed (cooldown "
                        f"{self._trigger_cooldown_seconds}s)"
                    )
                    continue

                self._last_trigger_ts[asset] = time.time()
                trigger_label = (
                    "SCALP" if scalp else "SWING"
                )
                logger.info(
                    f"🚨 TRIGGER [{trigger_label}] for {asset}! "
                    f"Details: {json.dumps(details, default=str)}"
                )

                # Generate dossier
                json_path, md_path = generate_dossier(
                    state, trigger_label, details, self.cfg
                )
                self._last_dossier = {
                    "asset": asset,
                    "trigger_mode": trigger_label,
                    "json_path": json_path,
                    "md_path": md_path,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                # Fire analysis pipeline (non-blocking)
                asyncio.create_task(
                    self._fire_analysis(asset, state, details, trigger_label)
                )

    async def _fire_analysis(
        self, asset: str, state: IndicatorState, details: Dict, trigger_label: str
    ) -> None:
        """Trigger the full ZScore + SpotDiff + Heatmap pipeline."""
        try:
            from strategies.funding_fees import FundingFeesEngine
            engine = FundingFeesEngine()

            if trigger_label == "SCALP":
                logger.info(f"🔍 [SCALP] Ejecutando escaneo Ultra-Deep para {asset}...")
                
                import sys
                from pathlib import Path
                fac_path = str(Path(self.cfg.reports_dir).parent / "funding_action_server")
                if fac_path not in sys.path:
                    sys.path.append(fac_path)
                    
                from actions.funding_actions import get_ultra_deep_confluence
                
                loop = asyncio.get_event_loop()
                raw_json = await loop.run_in_executor(None, get_ultra_deep_confluence, asset, 100)
                ud_data = json.loads(raw_json)
                asset_res = ud_data.get(asset, {})
                
                if asset_res.get("verdict") == "EXTREME_PRESSURE":
                    from alerts.telegram import TelegramService
                    tg = TelegramService()
                    
                    direction = asset_res.get("direction", "UNKNOWN")
                    confl = asset_res.get("confluence_pct", "0%")
                    obi_val = asset_res.get("avg_obi", 0.0)
                    desc_obi = "VENTA MASIVA" if obi_val < 0 else "COMPRA MASIVA"
                    
                    msg = (
                        f"🚨 *¡CONFLUENCIA EXTREMA DETECTADA!* 🚨\n"
                        f"*Activo:* {asset}\n"
                        f"*OBI Promedio (100 niveles):* {obi_val} ({desc_obi})\n"
                        f"*Acuerdo entre Exchanges:* {confl}\n"
                        f"*Acción sugerida:* {direction} inmediato.\n"
                    )
                    await tg.send_text(msg, parse_mode="Markdown")
                    logger.info(f"✅ Ultra-Deep alert sent for {asset}")

            max_funding = _max_abs(state.funding_rates) or 0.0
            max_delta = _max_abs(state.delta_funding_1h) or 0.0

            anomaly = {
                "symbol": asset,
                "exchange": "MultiExchange",
                "current_rate": max_funding,
                "prev_rate": max_funding - max_delta,
                "delta_bps": max_delta * 100,  # convert % to bps
                "zscore": 0.0,
                "severity": "HIGH",
                "direction": "UP" if max_funding > 0 else "DOWN",
            }

            await engine.trigger_market_state_analysis(anomaly)
            logger.info(f"✅ Analysis pipeline completed for {asset}")

        except Exception as e:
            logger.error(f"❌ Analysis pipeline error for {asset}: {e}", exc_info=True)

    # ── Console Status ────────────────────────────────────────────

    def _log_status(self) -> None:
        """Log current indicator status to console."""
        for asset in self.cfg.assets:
            st = self._states[asset]
            parts = [f"[{asset}]"]

            # Best funding across exchanges
            for ex_id in self.cfg.exchanges:
                fr = st.funding_rates.get(ex_id)
                if fr is not None:
                    parts.append(f"{ex_id[:4]}:FR={fr:+.6f}%")

            # Best OBI
            for ex_id in self.cfg.exchanges:
                obi = st.obis.get(ex_id)
                if obi is not None:
                    parts.append(f"{ex_id[:4]}:OBI={obi:+.4f}")

            # Triggers
            if st.trigger_scalp:
                parts.append("🟡SCALP")
            if st.trigger_swing:
                parts.append("🔴SWING")

            logger.info(" | ".join(parts))

    def get_summary_text(self, assets: Optional[List[str]] = None) -> str:
        """
        Return a formatted Markdown summary for Telegram.
        
        Includes OBI, OI, Funding and active Scalp/Swing triggers.
        """
        target_assets = assets if assets else self.cfg.assets
        
        header = "🛰️ *MONITOR: SCALP & SWING* 🛰️\n"
        header += "━━━━━━━━━━━━━━━━━━\n"
        header += f"`{'Asset':<6} | {'OBI':>6} | {'OI%':>5} | {'FR%':>7} | {'TRG'}`\n"
        header += f"`{'-'*6}-+-{'-'*6}-+-{'-'*5}-+-{'-'*7}-+-{'-'*3}`\n"
        
        rows = []
        for asset in target_assets:
            if asset not in self._states:
                continue
                
            st = self._states[asset]
            
            # Aggregate status across exchanges (using max abs)
            max_obi = _max_abs(st.obis)
            max_doi = _max_abs(st.delta_oi_1h)
            max_fr = _max_abs(st.funding_rates)
            
            # Get avg funding for sign
            any_fr = [v for v in st.funding_rates.values() if v is not None]
            avg_fr = sum(any_fr)/len(any_fr) if any_fr else 0.0
            fr_sign = "+" if avg_fr >= 0 else "-"
            
            # Trigger indicators
            trg = ""
            if st.trigger_scalp: trg += "🟡"
            if st.trigger_swing: trg += "🔴"
            if not trg: trg = "⚪"
            
            obi_str = f"{max_obi:>6.3f}" if max_obi is not None else "  —   "
            doi_str = f"{max_doi:>5.1f}%" if max_doi is not None else " — % "
            fr_str = f"{fr_sign}{max_fr:>6.4f}%" if max_fr is not None else " — % "
            
            rows.append(f"`{asset:<6} | {obi_str} | {doi_str} | {fr_str} |` {trg}")
            
        if not rows:
            return "❌ No hay datos en el monitor todavía."
            
        footer = "\n\n🟡 *SCALP:* OBI > 0.45 o Spike en Funding"
        footer += "\n🔴 *SWING:* ΔOI > 10% + Sesgo de Funding"
        footer += f"\n\n_Última actualización: {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC_"
        
        return header + "\n".join(rows) + footer

    # ── Main Loop ─────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the monitor polling loop."""
        if self._running:
            logger.warning("Monitor already running")
            return

        logger.info("═" * 60)
        logger.info("🚀 Funding + OI + OBI Monitor — Starting")
        logger.info(f"   Exchanges: {', '.join(self.cfg.exchanges)}")
        logger.info(f"   Assets: {', '.join(self.cfg.assets)}")
        logger.info(f"   Trigger mode: {self.cfg.trigger_mode}")
        logger.info(f"   Poll interval: {self.cfg.poll_interval_seconds}s")
        logger.info("═" * 60)

        await self._init_exchanges()
        self._running = True

        cycle_count = 0
        consecutive_errors = 0
        max_consecutive_errors = 10

        try:
            while self._running:
                cycle_start = time.time()
                try:
                    await self._poll_cycle()
                    consecutive_errors = 0
                    cycle_count += 1

                    # Log status every 5 cycles (~1 min)
                    if cycle_count % 5 == 0:
                        self._log_status()

                except Exception as e:
                    consecutive_errors += 1
                    logger.error(
                        f"Poll cycle error ({consecutive_errors}/"
                        f"{max_consecutive_errors}): {e}"
                    )
                    if consecutive_errors >= max_consecutive_errors:
                        logger.critical("Too many consecutive errors — stopping monitor")
                        break

                    # Exponential backoff on errors
                    backoff = min(
                        self.cfg.retry_base_delay * (2 ** consecutive_errors),
                        60.0,
                    )
                    await asyncio.sleep(backoff)
                    continue

                # Sleep for remaining interval
                elapsed = time.time() - cycle_start
                sleep_time = max(0, self.cfg.poll_interval_seconds - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        finally:
            self._running = False
            await self._close_exchanges()
            logger.info("Monitor stopped")

    async def start_background(self) -> None:
        """Start monitor as a background asyncio task."""
        if self._task and not self._task.done():
            logger.warning("Monitor task already running")
            return
        self._task = asyncio.create_task(self.start())

    async def stop(self) -> None:
        """Gracefully stop the monitor."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._close_exchanges()
        logger.info("Monitor stopped gracefully")


# ══════════════════════════════════════════════════════════════════
# STANDALONE ENTRY POINT
# ══════════════════════════════════════════════════════════════════

async def main():
    """Run the monitor standalone (for testing / CLI usage)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-18s | %(levelname)-5s | %(message)s",
        datefmt="%H:%M:%S",
    )
    engine = FundingMonitorEngine()
    try:
        await engine.start()
    except KeyboardInterrupt:
        await engine.stop()


if __name__ == "__main__":
    asyncio.run(main())
