#!/usr/bin/env python3
"""
strategies/orderflow.py — Order Flow Engine
Implementation based on orderflow_fib_c_v2.py
Kyle Delta, KMeans Block Detection, Wyckoff Phases, Fibonacci Confluence.
Generates a Dual-Panel (HTF/LTF) chart.
"""

import logging
import io
import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from sklearn.cluster import KMeans
from typing import Tuple, Optional

from core.config import settings, TickerConfig
from core.data_engine import DataEngine

logger = logging.getLogger("OrderFlow")

PHASE_COLORS = {
    'markup': '#00ff00',        # green
    'markdown': '#ff0000',      # red
    'accumulation': '#ffff00',  # yellow
    'distribution': '#ffa500'   # orange
}


class OrderFlowEngine:
    """Order Flow Analysis with Wyckoff Phase Detection and Fibonacci."""

    async def run(self, ticker: TickerConfig,
                  engine: DataEngine) -> Optional[Tuple[io.BytesIO, str]]:
        """Execute dual-panel order flow analysis pipeline."""
        try:
            # Fetch HTF (1d) and LTF (4h or 6h)
            timeframes = {'1d': 500, '4h': 1000}
            dataframes = await engine.fetch_ohlcv_multi_tf(ticker.symbol, timeframes)
            
            if not dataframes or '1d' not in dataframes or '4h' not in dataframes:
                logger.warning(f"Insufficient data for {ticker.name}")
                return None
                
            df_htf = dataframes['1d']
            df_ltf = dataframes['4h']
            
            if len(df_htf) < 50 or len(df_ltf) < 50:
                logger.warning(f"Not enough candles for {ticker.name}")
                return None

            # Calculate metrics
            df_htf, blocks_htf, levels_htf = self._calculate_metrics(df_htf)
            fib_htf = self._fibonacci(df_htf)
            
            df_ltf, blocks_ltf, levels_ltf = self._calculate_metrics(df_ltf)
            fib_ltf = self._fibonacci(df_ltf)

            # Generate dual chart
            chart_buf = self._generate_dual_chart(
                ticker, 
                df_htf, blocks_htf, levels_htf, fib_htf,
                df_ltf, blocks_ltf, levels_ltf, fib_ltf
            )

            # Caption
            last_phase = blocks_htf.iloc[-1]['wyckoff_phase'] if not blocks_htf.empty else "neutral"
            emoji = "🟢" if last_phase in ['markup', 'accumulation'] else("🔴" if last_phase in ['markdown', 'distribution'] else "⚪")
            caption = (
                f"{emoji} **{ticker.name} | ORDER FLOW + WYCKOFF**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📊 **Phase HTF:** {last_phase.capitalize()}\n"
                f"💰 **POC HTF:** ${levels_htf['poc']:,.2f}\n"
                f"🧱 **Bloques HTF:** {len(blocks_htf)} | **LTF:** {len(blocks_ltf)}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"_Dual-Panel: Order Flow Blocks & Fibonacci Confluence_"
            )

            return chart_buf, caption

        except Exception as e:
            logger.error(f"OrderFlow error ({ticker.name}): {e}", exc_info=True)
            return None

    def _calculate_metrics(self, df: pd.DataFrame):
        """Compute order flow blocks via cumulative delta and k-means clustering."""
        df = df.copy()

        # Directional volume
        df['buy_vol'] = df['volume'] * (df['close'] > df['open']).astype(float)
        df['sell_vol'] = df['volume'] - df['buy_vol']
        df['delta'] = df['buy_vol'] - df['sell_vol']
        df['cum_delta'] = df['delta'].cumsum()

        # Rolling stats
        df['delta_rolling'] = df['delta'].rolling(window=10, min_periods=1).mean()
        df['delta_std'] = df['delta'].rolling(window=10, min_periods=1).std().fillna(0)
        
        # Significance
        threshold = settings.thresholds.significant_delta_std if hasattr(settings.thresholds, 'significant_delta_std') else 1.5
        df['significant'] = np.abs(df['delta']) > (df['delta_rolling'].abs() + threshold * df['delta_std'])

        # Levels
        poc = np.average(df['close'], weights=df['volume'])
        mh = df['high'].rolling(window=20, min_periods=1).max().iloc[-1]
        ml = df['low'].rolling(window=20, min_periods=1).min().iloc[-1]
        wh = df['high'].rolling(window=5, min_periods=1).max().iloc[-1]
        wl = df['low'].rolling(window=5, min_periods=1).min().iloc[-1]
        levels = {'poc': poc, 'mh': mh, 'ml': ml, 'wh': wh, 'wl': wl}

        # Clustering
        sig = df[df['significant']].copy()
        if len(sig) > 5:
            features = sig[['close', 'delta']].values
            kmeans = KMeans(n_clusters=min(5, len(sig)), random_state=42, n_init=10)
            sig['cluster'] = kmeans.fit_predict(features)
        else:
            sig['cluster'] = 0

        # Wyckoff 
        sig['wyckoff_phase'] = 'accumulation'
        close_ma10 = sig['close'].rolling(10, min_periods=1).mean()
        
        sig.loc[(sig['delta'] > 0) & (sig['close'] > close_ma10), 'wyckoff_phase'] = 'markup'
        sig.loc[(sig['delta'] < 0) & (sig['close'] < close_ma10), 'wyckoff_phase'] = 'markdown'
        sig.loc[(sig['delta'] < 0) & (np.abs(sig['delta']) < sig['delta_std']), 'wyckoff_phase'] = 'distribution'

        return df, sig, levels

    def _fibonacci(self, df: pd.DataFrame, lookback: int = 100) -> dict:
        """Calculate Fibonacci retracement levels from recent swing."""
        recent = df.iloc[-lookback:]
        if recent.empty:
            return {}
            
        high_idx = recent['high'].idxmax()
        low_idx = recent['low'].idxmin()
        high_val = recent.loc[high_idx, 'high']
        low_val = recent.loc[low_idx, 'low']
        diff = high_val - low_val

        ratios = {'23.6': 0.236, '38.2': 0.382, '50.0': 0.5, '61.8': 0.618}

        if high_idx > low_idx:
            levels = {k: high_val - diff * v for k, v in ratios.items()}
            levels['0.0'] = high_val
            levels['100.0'] = low_val
        else:
            levels = {k: low_val + diff * v for k, v in ratios.items()}
            levels['0.0'] = low_val
            levels['100.0'] = high_val

        return levels

    def _generate_dual_chart(self, ticker: TickerConfig, 
                             df_htf: pd.DataFrame, blocks_htf: pd.DataFrame, levels_htf: dict, fib_htf: dict,
                             df_ltf: pd.DataFrame, blocks_ltf: pd.DataFrame, levels_ltf: dict, fib_ltf: dict) -> io.BytesIO:
        """Visualize dual-panel order flow blocks with Fibonacci confluence."""
        plt.style.use('dark_background')
        fig, axs = plt.subplots(2, 1, figsize=(14, 10), sharex=False, facecolor='#0a0a0a')
        fig.patch.set_facecolor('#0a0a0a')
        
        def plot_panel(ax, df, blocks, levels, fib, title, bar_width_base):
            ax.set_facecolor('#0a0a0a')
            ax.plot(df.index, df['close'], color='cyan', linewidth=1.5, label='Close Price', alpha=0.8)
            
            if not blocks.empty:
                delta_max = blocks['delta'].abs().max()
                if delta_max == 0: delta_max = 1
                price_range = df['high'].max() - df['low'].min()
                
                for idx, row in blocks.iterrows():
                    color = PHASE_COLORS.get(row['wyckoff_phase'], 'gray')
                    bar_start = mdates.date2num(idx)
                    # Use a small percentage of total timeframe width for bars
                    bar_width = bar_width_base
                    bar_height = (abs(row['delta']) / delta_max) * price_range * 0.05
                    
                    ax.barh(row['close'], bar_width, left=bar_start, height=bar_height, 
                            color=color, alpha=0.5, edgecolor='black', linewidth=0.5)

            # Key levels
            ax.axhline(levels['poc'], color='white', linestyle='-', linewidth=2, label='POC', alpha=0.8)
            ax.axhline(levels['mh'], color='orange', linestyle='--', linewidth=1.5, label='MH', alpha=0.7)
            ax.axhline(levels['ml'], color='orange', linestyle='--', linewidth=1.5, label='ML', alpha=0.7)
            ax.axhline(levels['wh'], color='#00ffcc', linestyle='-.', linewidth=1.5, label='WH', alpha=0.6)
            ax.axhline(levels['wl'], color='#00ffcc', linestyle='-.', linewidth=1.5, label='WL', alpha=0.6)
            
            # Fibo
            for name, price in fib.items():
                if name not in ['0.0', '100.0']:
                    ax.axhline(price, color='#b026ff', linestyle=':', linewidth=1.5, alpha=0.6)
                    ax.text(df.index[-1], price, f' Fib {name}%', fontsize=8, color='#b026ff', va='center')

            ax.set_ylabel('Price (USDT)', fontsize=11, fontweight='bold', color='white')
            ax.set_title(title, fontsize=12, fontweight='bold', color='white')
            ax.legend(loc='upper left', fontsize=8, facecolor='#111111', edgecolor='#333333', labelcolor='white')
            ax.grid(True, alpha=0.15, color='white')
            ax.tick_params(colors='white')
            for spine in ax.spines.values(): spine.set_color('#333333')

        # HTF Panel (Daily) -> width ~2 days
        plot_panel(axs[0], df_htf, blocks_htf, levels_htf, fib_htf, 'HTF (1D) - Order Flow Blocks & Fibonacci', 2.0)
        
        # LTF Panel (4H) -> width ~0.25 days (6 hours)
        plot_panel(axs[1], df_ltf, blocks_ltf, levels_ltf, fib_ltf, 'LTF (4H) - Order Flow Blocks & Fibonacci', 0.25)
        
        # X-axis formatting
        axs[1].xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.setp(axs[1].xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        ctime = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        fig.suptitle(f'Bull/Bear Order Flow Blocks para {ticker.name} ({ctime})\nKyle Microstructure + Fibonacci + Wyckoff',
                     fontsize=14, fontweight='bold', color='white', y=0.995)
        
        plt.tight_layout(rect=[0, 0, 1, 0.98])
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, facecolor='#0a0a0a', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf
