#!/usr/bin/env python3
"""
strategies/heatmap.py — S/R Heatmap Engine
Consolidates two user-provided scripts:
1. Dual-Panel Heatmap (1D, 1H) with Fractal Pivots and Wyckoff Zones.
2. Advanced Comprehensive Grid (4H Heatmap/Bias, 1D Heatmap/VP, 1W Heatmap/VP).
"""

import io
import logging
import datetime
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.ndimage import gaussian_filter1d
from typing import Tuple, Optional, Dict, List

from core.config import settings, TickerConfig
from core.data_engine import DataEngine

logger = logging.getLogger("Heatmap")


class HeatmapEngine:
    """S/R Heatmap Strategy Engine combining multiple approaches."""

    async def run(self, ticker: TickerConfig,
                  engine: DataEngine,
                  timeframes: Optional[Dict[str, int]] = None) -> Optional[List[Tuple[io.BytesIO, str]]]:
        """
        Execute both the Basic Dual-Panel and Advanced Grid Heatmap strategies.
        Returns a list of (BytesIO, caption) tuples.
        """
        try:
            # We need 1h, 4h, 1d, 1w.
            tf_config = {
                '1h': 720,    # ~1 month of 1H data (safe limit for chart)
                '4h': 4320,   # ~6 months of 4H data (4320 is large, capping at limit if needed)
                '1d': 365,
                '1w': 52
            }
            
            dataframes = await engine.fetch_ohlcv_multi_tf(ticker.symbol, tf_config)
            if not dataframes or '1d' not in dataframes:
                logger.warning(f"Insufficient data for {ticker.name}")
                return None

            results = []

            # 1. Dual-Panel Strategy (1D and 1H)
            if '1d' in dataframes and '1h' in dataframes:
                try:
                    df_htf = dataframes['1d']
                    df_ltf = dataframes['1h']
                    heat_htf, bins_htf = self._compute_sr_heatmap(df_htf)
                    heat_ltf, bins_ltf = self._compute_sr_heatmap(df_ltf)
                    
                    buf_basic = self._generate_basic_chart(ticker, df_htf, df_ltf, heat_htf, heat_ltf, bins_htf, bins_ltf)
                    cap_basic = (
                        f"🔥 **{ticker.name} | S/R HEATMAP DUAL**\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"📊 **Métricas:** Puntos Pivot Fractales + Zonas Wyckoff\n"
                        f"🕰 **Timeframes:** 1D / 1H\n"
                        f"━━━━━━━━━━━━━━━━━━"
                    )
                    results.append((buf_basic, cap_basic))
                except Exception as e:
                    logger.error(f"Error generating basic dual heatmap for {ticker.name}: {e}", exc_info=True)

            # 2. Advanced Comprehensive Strategy (4H, 1D, 1W)
            required_adv = ['4h', '1d', '1w']
            if all(tf in dataframes for tf in required_adv):
                try:
                    dfs_adv = {tf: dataframes[tf] for tf in required_adv}
                    dfs_adv['4h'] = self._add_technical_indicators(dfs_adv['4h'])
                    
                    heatmaps = {}
                    bins_dict = {}
                    for tf in required_adv:
                        h, b = self._compute_sr_heatmap(dfs_adv[tf])
                        heatmaps[tf] = h
                        bins_dict[tf] = b
                        
                    vprofiles = {}
                    for tf in ['1d', '1w']:
                        vbins, vvol = self._calculate_volume_profile(dfs_adv[tf])
                        vprofiles[tf] = (vbins, vvol)
                        
                    buf_adv = self._generate_adv_chart(ticker, dfs_adv, heatmaps, bins_dict, vprofiles)
                    cap_adv = (
                        f"🧠 **{ticker.name} | S/R HEATMAP AVANZADO**\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"📊 **Análisis:** Bias 4H + Perfil de Volumen\n"
                        f"🕰 **Timeframes:** 4H / 1D / 1W\n"
                        f"━━━━━━━━━━━━━━━━━━"
                    )
                    results.append((buf_adv, cap_adv))
                except Exception as e:
                    logger.error(f"Error generating advanced heatmap for {ticker.name}: {e}", exc_info=True)

            return results if results else None

        except Exception as e:
            logger.error(f"Heatmap execution error ({ticker.name}): {e}", exc_info=True)
            return None

    # ─── CORE CALCULATION LOGIC ──────────────────────────────────────

    def _detect_fractal_pivots(self, df: pd.DataFrame, window=5, reversal_threshold=0.02) -> list:
        highs = df['high'].values
        lows = df['low'].values
        pivot_highs = []
        pivot_lows = []
        
        for i in range(window, len(df) - window):
            if all(highs[i] > highs[i - j] for j in range(1, window + 1)) and \
               all(highs[i] > highs[i + j] for j in range(1, window + 1)):
                future_lows = lows[i + 1:i + window + 1]
                if len(future_lows) > 0 and (highs[i] - np.min(future_lows)) / highs[i] >= reversal_threshold:
                    pivot_highs.append((i, highs[i]))
                    
            if all(lows[i] < lows[i - j] for j in range(1, window + 1)) and \
               all(lows[i] < lows[i + j] for j in range(1, window + 1)):
                future_highs = highs[i + 1:i + window + 1]
                if len(future_highs) > 0 and (np.max(future_highs) - lows[i]) / lows[i] >= reversal_threshold:
                    pivot_lows.append((i, lows[i]))
        return pivot_highs + pivot_lows

    def _compute_sr_heatmap(self, df: pd.DataFrame, n_bins=50, rolling_window=50, 
                            vol_boost_factor=1.2, vol_threshold=0.8, smooth_sigma=3) -> Tuple[np.ndarray, np.ndarray]:
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        volumes = df['volume'].values
        
        min_p, max_p = closes.min(), closes.max()
        bins = np.linspace(min_p, max_p, n_bins + 1)
        bin_centers = (bins[:-1] + bins[1:]) / 2
        
        touch_matrix = np.zeros((n_bins, len(df)))
        for j in range(len(df)):
            touched_bins = np.where((bin_centers >= lows[j]) & (bin_centers <= highs[j]))[0]
            touch_matrix[touched_bins, j] = 1.0
            
        heat_matrix = np.zeros_like(touch_matrix)
        for i in range(n_bins):
            touches_rolling = pd.Series(touch_matrix[i]).rolling(rolling_window, min_periods=1).mean().values
            heat_matrix[i] = np.clip(touches_rolling, 0, 1)
            
        pivots = self._detect_fractal_pivots(df)
        pivot_window = rolling_window // 2
        for idx, pivot_price in pivots:
            bin_idx = np.digitize(pivot_price, bins) - 1
            if 0 <= bin_idx < n_bins:
                start, end = max(0, idx - pivot_window), min(len(df), idx + pivot_window + 1)
                heat_matrix[bin_idx, start:end] = np.minimum(1.0, heat_matrix[bin_idx, start:end] + 0.3)
                
        avg_vol = np.mean(volumes)
        low_vol_mask = volumes < vol_threshold * avg_vol
        for j in range(len(df)):
            if low_vol_mask[j]:
                touched_bins = np.where((bin_centers >= lows[j]) & (bin_centers <= highs[j]))[0]
                h_slice = heat_matrix[touched_bins, max(0, j-pivot_window):min(len(df), j+pivot_window+1)]
                h_slice *= vol_boost_factor
                heat_matrix[touched_bins, max(0, j-pivot_window):min(len(df), j+pivot_window+1)] = np.clip(h_slice, 0, 1)
                
        for i in range(n_bins):
            if np.sum(heat_matrix[i]) > 0:
                heat_matrix[i] = gaussian_filter1d(heat_matrix[i], sigma=smooth_sigma)
                
        heat_max = heat_matrix.max()
        if heat_max > 0:
            heat_matrix /= heat_max
            
        return heat_matrix, bin_centers

    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['SMA_50'] = df['close'].rolling(window=50).mean()
        df['SMA_200'] = df['close'].rolling(window=200).mean()
        return df

    def _determine_bias(self, df: pd.DataFrame) -> str:
        last_sma_50 = df['SMA_50'].iloc[-1]
        last_sma_200 = df['SMA_200'].iloc[-1]
        if pd.isna(last_sma_50) or pd.isna(last_sma_200):
            return "Indefinido"
        if last_sma_50 > last_sma_200:
            return "Alcista"
        elif last_sma_50 < last_sma_200:
            return "Bajista"
        return "Neutral"

    def _calculate_volume_profile(self, df: pd.DataFrame, num_bins=100) -> Tuple[np.ndarray, np.ndarray]:
        price_min = df['low'].min()
        price_max = df['high'].max()
        bins = np.linspace(price_min, price_max, num_bins)
        volume_profile = np.zeros(num_bins - 1)
        
        for _, row in df.iterrows():
            low, high, volume = row['low'], row['high'], row['volume']
            touched_bins = np.digitize(np.linspace(low, high, 10), bins) - 1
            for bin_idx in touched_bins:
                if 0 <= bin_idx < len(volume_profile):
                    volume_profile[bin_idx] += volume / len(touched_bins)
                    
        bin_centers = (bins[:-1] + bins[1:]) / 2
        return bin_centers, volume_profile

    # ─── PLOTTING LOGIC ──────────────────────────────────────────────

    def _generate_basic_chart(self, ticker: TickerConfig, df_htf: pd.DataFrame, df_ltf: pd.DataFrame,
                              heat_htf: np.ndarray, heat_ltf: np.ndarray, 
                              bins_htf: np.ndarray, bins_ltf: np.ndarray) -> io.BytesIO:
        plt.style.use('dark_background')
        fig, axs = plt.subplots(2, 1, figsize=(14, 12), facecolor='#0a0a0a')
        fig.patch.set_facecolor('#0a0a0a')
        
        ctime = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        fig.suptitle(f"{ticker.name} S/R Heatmap: Puntos Pivot + Wyckoff ({ctime})",
                     fontsize=16, color='white', fontweight='bold', y=0.98)

        def plot_panel(ax, df, heat, bins, title):
            sns.heatmap(heat, ax=ax, cmap='magma', vmin=0, vmax=1, cbar=True,
                        cbar_kws={'orientation': 'vertical', 'fraction': 0.02, 'pad': 0.02},
                        linewidths=0.1, linecolor='#1a1a1a', alpha=0.9)
            ax_price = ax.twinx()
            x = np.arange(len(df))
            ax_price.plot(x, df['close'], color='white', linewidth=2, alpha=0.9)
            
            n_ticks = 8
            y_ticks = np.linspace(0, len(bins) - 1, n_ticks, dtype=int)
            ax.set_yticks(y_ticks)
            ax.set_yticklabels([f"{bins[t]:.0f}" for t in y_ticks], color='white', fontsize=9)
            x_ticks = np.linspace(0, len(df) - 1, n_ticks, dtype=int)
            ax.set_xticks(x_ticks)
            ax.set_xticklabels([df.index[t].strftime('%m/%d') for t in x_ticks], rotation=0, color='white', fontsize=9)
            
            ax.set_title(title, fontsize=14, color='white', fontweight='bold', pad=15)
            ax.set_ylabel('Precio', color='white')
            for spine in ax.spines.values(): spine.set_color('#333333')
            for spine in ax_price.spines.values(): spine.set_visible(False)
            ax.tick_params(colors='white')
            ax_price.tick_params(colors='white', labelright=False)

        plot_panel(axs[0], df_htf, heat_htf, bins_htf, 'HTF (1D): Fractal S/R + Zonas de Volumen')
        plot_panel(axs[1], df_ltf, heat_ltf, bins_ltf, 'LTF (1H): Fractal S/R + Zonas de Volumen')

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=300, facecolor='#0a0a0a', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf

    def _generate_adv_chart(self, ticker: TickerConfig, dataframes: Dict[str, pd.DataFrame],
                            heatmaps: Dict[str, np.ndarray], bins: Dict[str, np.ndarray],
                            volume_profiles: Dict[str, Tuple[np.ndarray, np.ndarray]]) -> io.BytesIO:
        plt.style.use('dark_background')
        fig = plt.figure(figsize=(18, 14), facecolor='#0a0a0a')
        fig.patch.set_facecolor('#0a0a0a')
        
        gs = gridspec.GridSpec(3, 2, figure=fig, height_ratios=[1, 1, 1], width_ratios=[4, 1])
        axs_map = {'4h': fig.add_subplot(gs[0, 0]), '1d': fig.add_subplot(gs[1, 0]), '1w': fig.add_subplot(gs[2, 0])}

        # 4H Bias
        df4 = dataframes['4h']
        bias = self._determine_bias(df4)
        sns.heatmap(heatmaps['4h'], ax=axs_map['4h'], cmap='magma', vmin=0, vmax=1, cbar=False, alpha=0.9)
        axp4 = axs_map['4h'].twinx()
        x = np.arange(len(df4))
        axp4.plot(x, df4['close'], color='white', linewidth=2)
        axp4.plot(x, df4['SMA_50'], color='orange', linestyle='--', label='SMA 50')
        axp4.plot(x, df4['SMA_200'], color='cyan', linestyle='--', label='SMA 200')
        axp4.legend(loc='upper left')
        axp4.set_ylim(0, df4['high'].max() * 1.05)
        axs_map['4h'].set_ylim(0, len(bins['4h']) - 1)
        axs_map['4h'].set_title(f'Timeframe: 4H | Bias: {bias}', fontsize=14, color='cyan', fontweight='bold')

        # 1D, 1W VP
        for i, tf in enumerate(['1d', '1w']):
            df_tf = dataframes[tf]
            axh = axs_map[tf]
            axv = fig.add_subplot(gs[i+1, 1])
            sns.heatmap(heatmaps[tf], ax=axh, cmap='magma', vmin=0, vmax=1, cbar=False, alpha=0.9)
            axp = axh.twinx()
            axp.plot(np.arange(len(df_tf)), df_tf['close'], color='white', linewidth=2)
            
            vp_bins, vp_vol = volume_profiles[tf]
            axv.barh(vp_bins, vp_vol, height=(vp_bins[1]-vp_bins[0])*0.9, color='orange', alpha=0.7)
            
            ymax = df_tf['high'].max() * 1.05
            axv.set_ylim(0, ymax)
            axh.set_ylim(0, ymax)
            axp.set_ylim(0, ymax)
            axh.set_yticks([])
            axh.set_title(f'Timeframe: {tf.upper()} + VP', fontsize=14, color='white', fontweight='bold')
            axv.set_xlabel('Volumen', color='white', fontsize=10)
            axv.tick_params(axis='y', left=False, labelleft=False)

        ctime = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        fig.suptitle(f"Análisis Avanzado {ticker.name}: S/R, Bias y Volumen ({ctime})", 
                     fontsize=18, color='white', fontweight='bold', y=0.98)
                     
        for tf, ax in axs_map.items():
            df_tf = dataframes[tf]
            x_t = np.linspace(0, len(df_tf) - 1, 8, dtype=int)
            ax.set_xticks(x_t)
            ax.set_xticklabels([df_tf.index[i].strftime('%m/%d') for i in x_t], color='white', fontsize=9)
            for s in ax.spines.values(): s.set_color('#333333')

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.subplots_adjust(hspace=0.4, wspace=0.05)
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=300, facecolor='#0a0a0a', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf
