#!/usr/bin/env python3
"""
core/visualizer.py — Base Visualization Layer
Headless-safe (Agg backend), memory-managed, Nightclouds dark theme.
"""

import io
import gc
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from typing import Optional

from core.config import settings


def apply_theme():
    """Apply the Nightclouds institutional dark theme globally."""
    theme = settings.theme
    plt.style.use('dark_background')
    plt.rcParams.update({
        'figure.facecolor': theme.bg,
        'axes.facecolor': theme.bg,
        'axes.grid': False,
        'grid.color': theme.grid,
        'grid.linestyle': ':',
        'text.color': theme.text,
        'xtick.color': theme.text,
        'ytick.color': theme.text,
        'axes.labelcolor': theme.text,
        'axes.titlecolor': theme.accent,
        'savefig.facecolor': theme.bg
    })


# Apply on import
apply_theme()


class BaseChart:
    """
    Base class for all chart generation.
    Handles figure lifecycle, theme, and memory cleanup.
    
    Usage:
        chart = BaseChart(figsize=(14, 8), dpi=150)
        fig, ax = chart.create_figure()
        ax.plot(...)
        buf = chart.render()  # Returns io.BytesIO
    """

    def __init__(self, figsize=(14, 8), dpi: int = 150, nrows: int = 1,
                 ncols: int = 1, height_ratios: Optional[list] = None):
        self.figsize = figsize
        self.dpi = dpi
        self.nrows = nrows
        self.ncols = ncols
        self.height_ratios = height_ratios
        self.fig = None
        self.axes = None
        self._theme = settings.theme

    @property
    def colors(self) -> dict:
        """Quick access to theme colors."""
        return {
            'bg': self._theme.bg,
            'bull': self._theme.bull,
            'bear': self._theme.bear,
            'neutral': self._theme.neutral,
            'accent': self._theme.accent,
            'text': self._theme.text,
            'grid': self._theme.grid
        }

    def create_figure(self):
        """Create figure and axes with theme applied."""
        if self.height_ratios and self.nrows > 1:
            self.fig, self.axes = plt.subplots(
                self.nrows, self.ncols,
                figsize=self.figsize,
                gridspec_kw={'height_ratios': self.height_ratios}
            )
        else:
            self.fig, self.axes = plt.subplots(
                self.nrows, self.ncols,
                figsize=self.figsize
            )

        self.fig.patch.set_facecolor(self.colors['bg'])

        # Apply theme to all axes
        axs = self.axes if isinstance(self.axes, np.ndarray) else [self.axes]
        for ax in np.ravel(axs):
            ax.set_facecolor(self.colors['bg'])

        return self.fig, self.axes

    def style_axis(self, ax, title: str = "", xlabel: str = "",
                   ylabel: str = "", grid: bool = True):
        """Apply consistent styling to an axis."""
        if title:
            ax.set_title(title, fontsize=12, color=self.colors['accent'], fontweight='bold')
        if xlabel:
            ax.set_xlabel(xlabel, color=self.colors['text'])
        if ylabel:
            ax.set_ylabel(ylabel, color=self.colors['text'])
        if grid:
            ax.grid(True, which='major', linestyle='--',
                    linewidth=0.3, color=self.colors['grid'], alpha=0.3)
            ax.set_axisbelow(True)

    def render(self) -> io.BytesIO:
        """Render figure to BytesIO buffer and cleanup."""
        if self.fig is None:
            raise RuntimeError("No figure created. Call create_figure() first.")

        plt.tight_layout()
        buf = io.BytesIO()
        self.fig.savefig(buf, format='png', dpi=self.dpi,
                         facecolor=self.colors['bg'], bbox_inches='tight')
        plt.close(self.fig)
        self.fig = None
        self.axes = None
        gc.collect()
        buf.seek(0)
        return buf


# ═══════════════════════════════════════════════════
# Candlestick Drawing Utility
# ═══════════════════════════════════════════════════

def draw_candles(ax, df: pd.DataFrame, width: float = 0.6,
                 bull_color: str = '#2979FF', bear_color: str = '#FFFFFF'):
    """
    Draw candlestick chart on given axis.
    Uses integer x-axis (0..len(df)) for performance.
    """
    opens = df['open'].values
    closes = df['close'].values
    highs = df['high'].values
    lows = df['low'].values

    for i in range(len(df)):
        color = bull_color if closes[i] >= opens[i] else bear_color

        # Wick
        ax.plot([i, i], [lows[i], highs[i]], color=color, linewidth=0.8, alpha=0.9)

        # Body
        body_bottom = min(opens[i], closes[i])
        body_height = abs(closes[i] - opens[i])
        if body_height == 0:
            body_height = (highs[i] - lows[i]) * 0.001  # Doji visibility

        rect = plt.Rectangle(
            (i - width/2, body_bottom), width, body_height,
            facecolor=color, edgecolor=None, alpha=1.0
        )
        ax.add_patch(rect)


def format_date_axis(ax, df: pd.DataFrame, n_ticks: int = 10):
    """Add date labels to integer x-axis."""
    if len(df) == 0:
        return
    x_ticks = np.linspace(0, len(df) - 1, min(n_ticks, len(df)), dtype=int)
    date_labels = [df.index[t].strftime('%m/%d') for t in x_ticks]
    ax.set_xticks(x_ticks)
    ax.set_xticklabels(date_labels, rotation=0, fontsize=9)
