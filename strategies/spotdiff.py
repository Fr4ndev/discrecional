#!/usr/bin/env python3
"""
strategies/spotdiff.py — Spot-Futures Diff Engine
EWMA Smoothing, CVD, OBI, Z-Score Absorption, Kelly Criterion.
Consolidates: analysis_bot::SpotDiffAnalyzer + spotdiff/spotdiff_multiticker_kellysizing.py
"""

import logging
import io
import numpy as np
import pandas as pd
from typing import Tuple, Optional, List

from core.config import settings, TickerConfig
from core.data_engine import DataEngine
from core.indicators import (
    zscore_full, cvd, obi, ewma, sma, atr,
    kelly_fraction, atr_stop_levels
)
from core.visualizer import BaseChart

logger = logging.getLogger("SpotDiff")


class SpotDiffEngine:
    """Spot vs. Futures volume differential analysis."""

    async def run(self, ticker: TickerConfig,
                  engine: DataEngine) -> Optional[Tuple[io.BytesIO, str]]:
        """Single-ticker analysis with chart + caption."""
        try:
            tf_cfg = settings.timeframes.get('spotdiff', {})
            tf = tf_cfg.get('tf', '1d')
            limit = tf_cfg.get('limit', 365)

            # Fetch spot + futures
            df_spot, df_fut = await engine.fetch_spot_futures_pair(
                ticker.symbol, ticker.spot, tf, limit
            )
            if df_spot is None or df_fut is None:
                logger.warning(f"Missing data for {ticker.name}")
                return None

            # Fetch order book for OBI
            ob = await engine.fetch_order_book(ticker.spot)
            obi_val = obi(ob) if ob else 0.0

            # Process
            df = self._process(df_spot, df_fut)
            if df is None or len(df) < 10:
                return None

            # Chart
            chart_buf = self._generate_chart(ticker, df, obi_val)

            # Caption
            last_z = float(df['iai_zscore'].iloc[-1])
            status, emoji = self._classify(last_z)

            caption = (
                f"{emoji} **{ticker.name} | SPOT vs FUTURES DIFF**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"⚖️ **Status:** {status}\n"
                f"📊 **Absorption Z-Score:** {last_z:.2f}\n"
                f"🌊 **OBI (Imbalance):** {obi_val:.2%}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"_Spot Market Dominance Analysis_"
            )

            return chart_buf, caption

        except Exception as e:
            logger.error(f"SpotDiff error ({ticker.name}): {e}", exc_info=True)
            return None

    async def scan_all(self, engine: DataEngine) -> str:
        """
        Multi-ticker scanner with Kelly sizing.
        Returns formatted text summary for all tickers.
        """
        rows = []
        for ticker in settings.universe:
            try:
                tf_cfg = settings.timeframes.get('spotdiff', {})
                tf = tf_cfg.get('tf', '1d')
                limit = tf_cfg.get('limit', 365)

                df_spot, df_fut = await engine.fetch_spot_futures_pair(
                    ticker.symbol, ticker.spot, tf, limit
                )
                if df_spot is None or df_fut is None:
                    rows.append(self._empty_row(ticker))
                    continue

                ob = await engine.fetch_order_book(ticker.spot)
                obi_val = obi(ob) if ob else 0.0

                df = self._process(df_spot, df_fut)
                if df is None or len(df) < 10:
                    rows.append(self._empty_row(ticker))
                    continue

                # Scoring
                last_z = float(df['iai_zscore'].iloc[-1])
                score = self._score(last_z, obi_val)
                win_prob = {3: 0.75, 2: 0.60, 1: 0.45, 0: 0.30}.get(score, 0.3)
                kelly = kelly_fraction(win_prob, settings.thresholds.kelly_risk_reward)

                # ATR Stops
                stops = atr_stop_levels(df_spot)

                status, emoji = self._classify(last_z)
                rows.append({
                    'Ticker': ticker.name,
                    'Z-Score': f"{last_z:+.2f}",
                    'OBI': f"{obi_val:+.2%}",
                    'Score': f"{'⭐' * score}",
                    'Kelly': f"{kelly:.1%}",
                    'SL': f"${stops['stop_loss']:,.0f}",
                    'TP': f"${stops['take_profit']:,.0f}",
                    'Signal': f"{emoji} {status}"
                })

            except Exception as e:
                logger.warning(f"Scan error {ticker.name}: {e}")
                rows.append(self._empty_row(ticker))

        # Format output
        if not rows:
            return "No data available."

        lines = [f"{'Ticker':<12} {'Z-Score':>8} {'OBI':>8} {'Score':>6} {'Kelly':>7} {'SL':>10} {'TP':>10} {'Signal'}"]
        lines.append("─" * 80)
        for r in rows:
            lines.append(
                f"{r['Ticker']:<12} {r['Z-Score']:>8} {r['OBI']:>8} "
                f"{r['Score']:>6} {r['Kelly']:>7} {r['SL']:>10} {r['TP']:>10} {r['Signal']}"
            )

        return "```\n" + "\n".join(lines) + "\n```"

    def _process(self, df_spot: pd.DataFrame,
                 df_fut: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Merge and calculate metrics."""
        try:
            # Align by timestamp
            df_s = df_spot[['open', 'high', 'low', 'close', 'volume']].copy()
            df_f = df_fut[['close', 'volume']].copy()

            df_s.columns = ['open', 'high', 'low', 'close_s', 'vol_s']
            df_f.columns = ['close_f', 'vol_f']

            df = df_s.join(df_f, how='inner')
            if len(df) < 10:
                return None

            # Volume difference
            df['vol_diff_pct'] = (df['vol_s'] - df['vol_f']) / df['vol_s'].replace(0, np.nan) * 100

            # CVD
            df['delta'] = (df['close_s'] - df['open']) / (df['high'] - df['low']).replace(0, np.nan) * df['vol_s']
            df['cvd'] = df['delta'].cumsum()

            # EWMA smoothed diff
            df['vol_diff_smooth'] = ewma(df['vol_diff_pct'].fillna(0), 0.1)

            # Z-Score on absorption ratio
            ratio = (df['vol_s'] / df['vol_f'].replace(0, np.nan)).fillna(0)
            ratio = ratio.replace([np.inf, -np.inf], 0)
            df['iai_zscore'] = zscore_full(ratio)

            return df

        except Exception as e:
            logger.error(f"Process error: {e}")
            return None

    def _classify(self, z_score: float):
        """Classify z-score into status and emoji."""
        threshold = settings.thresholds.absorption_z_threshold
        if z_score > threshold:
            return "EXTREME BUYING (Spot Driven)", "🟢"
        elif z_score < -threshold:
            return "EXTREME SELLING (Spot Driven)", "🔴"
        return "NEUTRAL", "⚪️"

    def _score(self, z_score: float, obi_val: float) -> int:
        """Simple scoring: 0-3."""
        score = 0
        if abs(z_score) > 1.0:
            score += 1
        if abs(z_score) > 2.0:
            score += 1
        if abs(obi_val) > 0.1:
            score += 1
        return min(score, 3)

    def _empty_row(self, ticker: TickerConfig) -> dict:
        return {
            'Ticker': ticker.name,
            'Z-Score': 'N/A', 'OBI': 'N/A', 'Score': '-',
            'Kelly': '-', 'SL': '-', 'TP': '-', 'Signal': '⚪️ NO DATA'
        }

    def _generate_chart(self, ticker: TickerConfig,
                        df: pd.DataFrame, obi_val: float) -> io.BytesIO:
        """Two-panel chart: Price + Absorption, Volume Diff."""
        chart = BaseChart(figsize=(14, 8), dpi=150, nrows=2, height_ratios=[1, 1])
        fig, (ax1, ax2) = chart.create_figure()

        # Panel 1: Price + Absorption signals
        ax1.plot(df.index, df['close_s'], color='white', linewidth=1, label='Spot Price')
        threshold = settings.thresholds.absorption_z_threshold
        signals = df[df['iai_zscore'] > threshold]
        ax1.scatter(signals.index, signals['close_s'], color=settings.theme.bull,
                   s=80, marker='o', label=f'Buying Climax (Z>{threshold})', zorder=3)
        chart.style_axis(ax1, title=f"{ticker.name} Spot Absorption Z-Score | OBI: {obi_val:.2%}",
                        ylabel="Price")
        ax1.legend(loc='upper left', fontsize=9)

        # Panel 2: Volume diff
        colors = np.where(df['vol_diff_pct'] > 0, settings.theme.bull, settings.theme.bear)
        ax2.bar(df.index, df['vol_diff_pct'], color=colors, alpha=0.8, width=0.8)
        ax2.axhline(0, color='gray', linestyle='--', alpha=0.5)
        chart.style_axis(ax2, title="Spot-Futures Volume Diff %", ylabel="Diff %")

        return chart.render()
