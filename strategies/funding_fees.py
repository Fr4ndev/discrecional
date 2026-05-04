#!/usr/bin/env python3
"""
strategies/funding_fees.py — FundingFeesMarketStateSkill v2.0
═══════════════════════════════════════════════════════════════
Fetches real-time multi-DEX funding rates from:
  PRIMARY  → https://fundingfees.web3crypt.net/ (HTML scrape)
  FALLBACK → CCXT (binanceusdm + bybit)

Detects variance/anomalies, then triggers the full Market State
Checker pipeline: ZScore + SpotDiff + Heatmap + multi-timeframe.

Author : ccxtv2 agent — March 2026
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

import ccxt.async_support as ccxt

from core.config import settings, TickerConfig
from core.data_engine import DataEngine

logger = logging.getLogger("FundingFees")

# ──────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────
USE_JSON_ENDPOINT: bool = False          # flip to True when dev enables endpoint
WEB3CRYPT_URL: str = "https://fundingfees.web3crypt.net/"
JSON_ENDPOINT_URL: str = ""             # fill when available

POLL_INTERVAL_SECONDS: int = 45
VARIANCE_THRESHOLD_BPS: float = 5.0    # 0.005%
ZSCORE_WINDOW: int = 30               # rolling z-score lookback

DATA_DIR = Path(__file__).parent.parent / "data"
LAST_RATES_FILE = DATA_DIR / "last_rates.json"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Known symbol mappings for CCXT fallback
CCXT_SYMBOLS: List[str] = [
    "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT",
    "BNB/USDT:USDT", "HYPE/USDT:USDT", "LINK/USDT:USDT",
]


# ──────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────

def _rate_to_float(value: str) -> Optional[float]:
    """Convert '0.0013%' → 0.0013 or '—'/'-' → None."""
    v = value.strip()
    if v in ("—", "-", "", "N/A", "n/a"):
        return None
    try:
        return float(v.replace("%", "").replace(",", "").strip())
    except ValueError:
        return None


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────────────────────────
# MAIN ENGINE CLASS
# ──────────────────────────────────────────────────────────────────

class FundingFeesEngine:
    """
    Multi-DEX Funding Fees Monitor & Market State Trigger.

    Usage:
        engine = FundingFeesEngine()
        df = engine.fetch_funding_fees()
        anomalies = engine.detect_variances(df)
        for a in anomalies:
            asyncio.run(engine.trigger_market_state_analysis(a))
    """

    def __init__(self) -> None:
        _ensure_data_dir()
        self._last_run_ts: float = 0.0

    # ─── PUBLIC API ───────────────────────────────────────────────

    async def fetch_funding_fees(self) -> pd.DataFrame:
        """
        Fetch multi-DEX funding rates.

        Returns
        -------
        pd.DataFrame
            Columns: asset | <exchange1> | <exchange2> | ... | timestamp
            Rate values are floats in % (e.g. 0.0013), or NaN if unavailable.
        """
        if USE_JSON_ENDPOINT and JSON_ENDPOINT_URL:
            return await asyncio.to_thread(self._fetch_json_endpoint)

        df = await asyncio.to_thread(self._fetch_web3crypt_html)
        if df is None or df.empty:
            logger.warning("⚠️  HTML scrape failed — falling back to CCXT")
            df = await self._async_fetch_ccxt()

        if df is not None and not df.empty:
            df["timestamp"] = datetime.now(timezone.utc).isoformat()
            logger.info(
                f"✅  Fetched funding rates — {len(df)} assets, "
                f"exchanges: {[c for c in df.columns if c not in ('asset','timestamp')]}"
            )
            return df

        logger.error("❌  All funding rate sources failed")
        return pd.DataFrame()

    def detect_variances(self, current_df: pd.DataFrame) -> List[Dict]:
        """
        Compare current rates with persisted state. Returns anomaly list.

        An anomaly is triggered when:
          |Δrate| > VARIANCE_THRESHOLD_BPS  OR  |z-score| > 2.0

        Parameters
        ----------
        current_df : pd.DataFrame
            Output of fetch_funding_fees().

        Returns
        -------
        List[Dict]
            Each dict: { symbol, exchange, current_rate, prev_rate,
                         delta_bps, zscore, severity }
        """
        anomalies: List[Dict] = []

        if current_df.empty:
            return anomalies

        last_state = self._load_last_rates()
        is_first_run = not last_state.get("rates")

        current_rates = self._df_to_rates_dict(current_df)
        history = last_state.get("zscore_history", {})

        for row in current_df.itertuples(index=False):
            asset = row.asset
            for col in current_df.columns:
                if col in ("asset", "timestamp"):
                    continue
                exchange = col
                rate_val = getattr(row, col, None)

                if pd.isna(rate_val) or rate_val is None:
                    continue

                prev_rate = last_state.get("rates", {}).get(asset, {}).get(exchange)
                key = f"{asset}_{exchange}"

                # Build rolling history for z-score
                hist_list: List[float] = history.get(key, [])
                hist_list.append(float(rate_val))
                hist_list = hist_list[-ZSCORE_WINDOW:]      # keep window
                history[key] = hist_list

                if is_first_run or prev_rate is None:
                    continue  # need at least one previous point

                delta_bps = abs(float(rate_val) - float(prev_rate)) * 100  # % to bps

                # Z-score of current rate in rolling window
                if len(hist_list) >= 3:
                    arr = np.array(hist_list)
                    std = arr.std()
                    z = (float(rate_val) - arr.mean()) / std if std > 1e-9 else 0.0
                else:
                    z = 0.0

                triggered = (
                    delta_bps >= VARIANCE_THRESHOLD_BPS or abs(z) >= 2.0
                )

                if triggered:
                    severity = "HIGH" if (delta_bps >= VARIANCE_THRESHOLD_BPS * 3 or abs(z) >= 3.0) else "MEDIUM"
                    anomalies.append({
                        "symbol": asset,
                        "exchange": exchange,
                        "current_rate": float(rate_val),
                        "prev_rate": float(prev_rate),
                        "delta_bps": round(delta_bps, 4),
                        "zscore": round(z, 3),
                        "severity": severity,
                        "direction": "UP" if float(rate_val) > float(prev_rate) else "DOWN",
                    })
                    logger.info(
                        f"🚨  VARIANCE  {asset}/{exchange}  "
                        f"Δ={delta_bps:.2f}bps  z={z:.2f}  [{severity}]"
                    )

        # Persist new state
        self._save_last_rates(current_rates, history)
        return anomalies

    async def trigger_market_state_analysis(self, anomaly: Dict) -> None:
        """
        Fire the full Market State Checker for an anomalous symbol.

        Runs ZScoreEngine, SpotDiffEngine, HeatmapEngine and sends results
        to Telegram.

        Parameters
        ----------
        anomaly : dict
            An element from detect_variances() output.
        """
        from strategies.zscore import ZScoreEngine
        from strategies.spotdiff import SpotDiffEngine
        from strategies.heatmap import HeatmapEngine
        from alerts.telegram import TelegramService
        from alerts.gateway import SentinelGateway, AlertMessage

        symbol = anomaly["symbol"]
        exchange = anomaly["exchange"]
        delta = anomaly["delta_bps"]
        z = anomaly["zscore"]
        severity = anomaly["severity"]
        direction = anomaly["direction"]

        # match raw symbol to a TickerConfig
        ticker = self._resolve_ticker(symbol)
        if ticker is None:
            logger.warning(f"⚠️  No TickerConfig found for symbol '{symbol}' — skip trigger")
            return

        sev_emoji = "🔴" if severity == "HIGH" else "🟡"
        dir_emoji = "⬆️" if direction == "UP" else "⬇️"
        trigger_msg = (
            f"{sev_emoji} *FUNDING RATE ANOMALY — {symbol}*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🏦 *Exchange:* {exchange}\n"
            f"{dir_emoji} *Δ Rate:* {delta:.2f} bps\n"
            f"📊 *Z-Score:* {z:+.2f}\n"
            f"⚡ *Severity:* {severity}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"_Triggering full Market State analysis…_"
        )

        # Text alert → unified gateway (dedup + rate limit)
        gw = SentinelGateway.instance()
        priority = 2 if severity == "HIGH" else 3
        await gw.dispatch(AlertMessage(
            source="FundingFees",
            priority=priority,
            text=trigger_msg,
            dedup_key=f"funding_{symbol}_{exchange}",
        ))
        tg = TelegramService()  # Kept for chart photo sending below
        logger.info(f"🚀  Triggering Market State for {symbol} [{severity}]")

        try:
            async with DataEngine() as engine:
                # Run all three strategies concurrently
                zscore_task = ZScoreEngine().run(ticker, engine)
                spotdiff_task = SpotDiffEngine().run(ticker, engine)
                heatmap_task = HeatmapEngine().run(ticker, engine)

                z_result, sd_result, hm_results = await asyncio.gather(
                    zscore_task, spotdiff_task, heatmap_task,
                    return_exceptions=True,
                )

                # Send charts
                for label, result in [("ZScore", z_result), ("SpotDiff", sd_result)]:
                    if isinstance(result, Exception):
                        logger.error(f"  {label} error: {result}")
                    elif result:
                        buf, caption = result
                        await tg.send_photo(buf, f"[FF→{label}] {caption}")

                if isinstance(hm_results, Exception):
                    logger.error(f"  Heatmap error: {hm_results}")
                elif hm_results:
                    for buf, caption in hm_results:
                        await tg.send_photo(buf, f"[FF→Heatmap] {caption}")

        except Exception as e:
            logger.error(f"trigger_market_state_analysis error: {e}", exc_info=True)

    async def get_current_table_text(self, assets: Optional[List[str]] = None) -> str:
        """
        Return formatted Markdown table of current funding rates.
        Optionally filter by a list of assets.
        """
        df = await self.fetch_funding_fees()
        if df.empty:
            return "❌ No se pudieron obtener las funding rates."

        if assets:
            assets_up = [a.upper().strip() for a in assets]
            df = df[df["asset"].str.upper().isin(assets_up)]
            if df.empty:
                return f"❌ No hay datos para: {', '.join(assets_up)}"

        exchanges = [c for c in df.columns if c not in ("asset", "timestamp")]
        ts = df["timestamp"].iloc[0] if "timestamp" in df.columns else "N/A"

        header = f"📡 *Funding Rates — {ts[:16]}*\n"
        header += "━━━━━━━━━━━━━━━━━━\n"
        header += f"`{'Asset':<8}" + "".join(f" {ex[:8]:>9}" for ex in exchanges) + "`\n"
        header += f"`{'─'*8}" + "".join(f" {'─'*9}" for _ in exchanges) + "`\n"

        rows = []
        for _, row in df.iterrows():
            asset_str = str(row["asset"])[:8].ljust(8)
            rate_strs = []
            for ex in exchanges:
                val = row.get(ex)
                if pd.isna(val) or val is None:
                    rate_strs.append("   —     ")
                else:
                    rate_strs.append(f"{val:>8.4f}%")
            rows.append(f"`{asset_str}" + "".join(f" {r}" for r in rate_strs) + "`")

        return header + "\n".join(rows)

    async def run_daemon(self) -> None:
        """
        Polling daemon: fetch → detect → trigger.
        Designed to run inside APScheduler (every POLL_INTERVAL_SECONDS).
        """
        logger.info("🔄  FundingFees daemon tick")
        try:
            df = await self.fetch_funding_fees()
            if df.empty:
                return
            anomalies = self.detect_variances(df)
            for anomaly in anomalies:
                await self.trigger_market_state_analysis(anomaly)
            if not anomalies:
                logger.debug("✅  No significant variance detected this cycle")
        except Exception as e:
            logger.error(f"run_daemon error: {e}", exc_info=True)

    # ─── PRIVATE — DATA FETCHING ──────────────────────────────────

    def _fetch_web3crypt_html(self) -> Optional[pd.DataFrame]:
        """Scrape the Markdown table from https://fundingfees.web3crypt.net/"""
        try:
            resp = requests.get(
                WEB3CRYPT_URL,
                headers=_HEADERS,
                timeout=3,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # Try pandas.read_html first (fastest)
            try:
                import io as _io
                tables = pd.read_html(_io.StringIO(resp.text))
                if tables:
                    df = tables[0]
                    df = self._normalize_dataframe(df)
                    if df is not None and not df.empty:
                        return df
            except Exception:
                pass  # fall through to manual BS4 parse

            # Manual BS4 table parse
            table = soup.find("table")
            if table is None:
                logger.debug("No <table> tag found in HTML response")
                return None

            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            if not headers:
                return None

            rows = []
            for tr in table.find("tbody").find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                if cells:
                    rows.append(cells)

            if not rows:
                return None

            df = pd.DataFrame(rows, columns=headers)
            return self._normalize_dataframe(df)

        except requests.RequestException as e:
            logger.warning(f"_fetch_web3crypt_html network error: {e}")
            return None
        except Exception as e:
            logger.warning(f"_fetch_web3crypt_html parse error: {e}")
            return None

    def _normalize_dataframe(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Standardize column names and convert rates to float."""
        if df is None or df.empty:
            return None

        # Identify asset column (first column, or 'Asset'/'Symbol')
        first_col = df.columns[0]
        rename_map = {first_col: "asset"}
        df = df.rename(columns=rename_map)

        exchange_cols = [c for c in df.columns if c != "asset"]

        for col in exchange_cols:
            df[col] = df[col].apply(
                lambda x: _rate_to_float(str(x)) if pd.notna(x) else np.nan
            )

        df = df.dropna(subset=["asset"])
        df = df[df["asset"].str.strip() != ""]
        df = df.reset_index(drop=True)

        if df.empty:
            return None
        return df

    def _fetch_json_endpoint(self) -> pd.DataFrame:
        """Future JSON endpoint (activated by USE_JSON_ENDPOINT=True)."""
        try:
            resp = requests.get(JSON_ENDPOINT_URL, headers=_HEADERS, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            # Expected format: [{"asset": "BTC", "Hyperliquid": 0.0013, ...}, ...]
            df = pd.DataFrame(data)
            if "asset" not in df.columns and len(df.columns) > 0:
                df = df.rename(columns={df.columns[0]: "asset"})
            return df
        except Exception as e:
            logger.error(f"JSON endpoint error: {e}")
            return pd.DataFrame()

    async def _async_fetch_ccxt(self) -> pd.DataFrame:
        """Fetch ALL current funding rates concurrently from all exchanges using batch API."""
        # 1. Use short timeouts (5s) for instant failure instead of blocking
        configs = {
            "timeout": 5000,
            "enableRateLimit": True,
        }
        
        exchanges = {
            "binance": ccxt.binanceusdm(configs),
            "bybit": ccxt.bybit(configs),
            "okx": ccxt.okx(configs),
            "hyperliquid": ccxt.hyperliquid(configs),
        }

        # 2. Strict universe to avoid loading 300+ markets, matching Action Server tests
        target_symbols = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "BNB/USDT:USDT", "HYPE/USDT:USDT", "LINK/USDT:USDT"]
        rows: Dict[str, Dict] = {}

        async def fetch_ex(name, ex):
            try:
                # 3. Batch API (eliminates sequential fetch_funding_rate loops)
                # Bybit, Binance, OKX support fetch_funding_rates for multiple symbols out-of-the-box
                if getattr(ex, 'has', {}).get('fetchFundingRates'):
                    rates = await ex.fetch_funding_rates(target_symbols)
                    res_map = {}
                    for sym in target_symbols:
                        r = rates.get(sym, {}).get("fundingRate")
                        res_map[sym] = float(r) * 100 if r is not None else None
                    return name, res_map
                else:
                    # 4. Ultimate fallback (parallel loop if batch fails)
                    await ex.load_markets()
                    valid_syms = [s for s in target_symbols if s in ex.markets]
                    coros = [ex.fetch_funding_rate(sym) for sym in valid_syms]
                    res_list = await asyncio.gather(*coros, return_exceptions=True)
                    res_map = {}
                    for sym, r_info in zip(valid_syms, res_list):
                        if isinstance(r_info, Exception):
                            res_map[sym] = None
                        else:
                            r = r_info.get("fundingRate")
                            res_map[sym] = float(r) * 100 if r is not None else None
                    return name, res_map
            except Exception as e:
                logger.warning(f"CCXT {name} fetch error: {e}")
                return name, {}
            finally:
                await ex.close()

        # 5. Execute all exchanges concurrently (1 wait for all)
        tasks = [fetch_ex(name, ex) for name, ex in exchanges.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, Exception):
                continue
            name, rates_map = res
            for sym, rate in rates_map.items():
                if rate is None:
                    continue
                asset = sym.split("/")[0]
                if asset not in rows:
                    rows[asset] = {}
                rows[asset][name] = rate

        if not rows:
            return pd.DataFrame()

        records = [{"asset": asset, **rates} for asset, rates in rows.items()]
        return pd.DataFrame(records)

    # ─── PRIVATE — PERSISTENCE ────────────────────────────────────

    def _load_last_rates(self) -> Dict:
        if LAST_RATES_FILE.exists():
            try:
                with open(LAST_RATES_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_last_rates(self, rates: Dict, history: Dict) -> None:
        try:
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "rates": rates,
                "zscore_history": history,
            }
            with open(LAST_RATES_FILE, "w") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save last_rates.json: {e}")

    def _df_to_rates_dict(self, df: pd.DataFrame) -> Dict:
        """Convert DataFrame to nested dict: asset → {exchange: rate}."""
        result: Dict[str, Dict] = {}
        exchange_cols = [c for c in df.columns if c not in ("asset", "timestamp")]
        for _, row in df.iterrows():
            asset = str(row["asset"])
            result[asset] = {}
            for col in exchange_cols:
                val = row.get(col)
                if pd.notna(val) and val is not None:
                    result[asset][col] = float(val)
        return result

    def _resolve_ticker(self, symbol: str) -> Optional[TickerConfig]:
        """Match raw asset name (e.g. 'BTC') to a TickerConfig in settings."""
        for ticker in settings.universe:
            name_up = ticker.name.upper()
            sym_up = symbol.upper().strip()
            if sym_up in name_up or name_up in sym_up:
                return ticker
        return None
