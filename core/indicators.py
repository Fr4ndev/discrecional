#!/usr/bin/env python3
"""
core/indicators.py — Vectorized Technical Indicators
Pure functions: accept DataFrame/Series, return Series. No iterrows().
"""

import numpy as np
import pandas as pd
from scipy.stats import zscore as scipy_zscore


# ═══════════════════════════════════════════════════
# Moving Averages  
# ═══════════════════════════════════════════════════

def sma(series: pd.Series, window: int = 20) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=window, min_periods=1).mean()


def ema(series: pd.Series, span: int = 20) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=span, adjust=False).mean()


def ewma(series: pd.Series, alpha: float = 0.1) -> pd.Series:
    """EWMA with explicit alpha."""
    return series.ewm(alpha=alpha, adjust=False).mean()


# ═══════════════════════════════════════════════════
# Oscillators  
# ═══════════════════════════════════════════════════

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder's smoothing)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def macd(series: pd.Series, fast: int = 12, slow: int = 26,
         signal: int = 9) -> pd.DataFrame:
    """MACD line, signal line, histogram."""
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return pd.DataFrame({
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    }, index=series.index)


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index."""
    high, low, close = df['high'], df['low'], df['close']

    plus_dm = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)

    # Zero out when one is larger
    plus_dm[plus_dm < minus_dm] = 0
    minus_dm[minus_dm < plus_dm] = 0

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)

    atr_val = tr.ewm(alpha=1/period, min_periods=period).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1/period, min_periods=period).mean() / atr_val
    minus_di = 100 * minus_dm.ewm(alpha=1/period, min_periods=period).mean() / atr_val

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1/period, min_periods=period).mean().fillna(0)


# ═══════════════════════════════════════════════════
# Bands & Channels  
# ═══════════════════════════════════════════════════

def bollinger_bands(series: pd.Series, window: int = 20,
                    num_std: float = 2.0) -> pd.DataFrame:
    """Bollinger Bands: middle, upper, lower."""
    middle = sma(series, window)
    std = series.rolling(window=window, min_periods=1).std()
    return pd.DataFrame({
        'bb_middle': middle,
        'bb_upper': middle + (std * num_std),
        'bb_lower': middle - (std * num_std)
    }, index=series.index)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range."""
    high, low, close = df['high'], df['low'], df['close']
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, min_periods=period).mean()


# ═══════════════════════════════════════════════════
# Z-Score & Statistical  
# ═══════════════════════════════════════════════════

def zscore_rolling(series: pd.Series, window: int = 100) -> pd.Series:
    """Rolling Z-Score."""
    mean = series.rolling(window=window, min_periods=1).mean()
    std = series.rolling(window=window, min_periods=1).std()
    return ((series - mean) / std.replace(0, np.nan)).fillna(0)


def zscore_full(series: pd.Series) -> pd.Series:
    """Full-sample Z-Score."""
    arr = series.values.astype(float)
    valid = ~np.isnan(arr)
    result = np.full_like(arr, np.nan)
    if valid.sum() > 1:
        result[valid] = scipy_zscore(arr[valid])
    return pd.Series(result, index=series.index).fillna(0)


# ═══════════════════════════════════════════════════
# Volume Metrics  
# ═══════════════════════════════════════════════════

def cvd(df: pd.DataFrame) -> pd.Series:
    """Cumulative Volume Delta (buy_vol - sell_vol cumulated)."""
    buy_vol = df['volume'] * (df['close'] > df['open']).astype(float)
    sell_vol = df['volume'] - buy_vol
    delta = buy_vol - sell_vol
    return delta.cumsum()


def obi(order_book: dict, depth: int = 20) -> float:
    """Order Book Imbalance from snapshot."""
    bids = sum(b[1] for b in order_book.get('bids', [])[:depth])
    asks = sum(a[1] for a in order_book.get('asks', [])[:depth])
    total = bids + asks
    return (bids - asks) / total if total > 0 else 0.0


def volume_profile(df: pd.DataFrame, bins: int = 50) -> pd.DataFrame:
    """
    Volume Profile — histogram of volume at price levels.
    Returns DataFrame with columns: [price_level, volume, pct]
    """
    prices = df['close'].values
    volumes = df['volume'].values
    vol_hist, bin_edges = np.histogram(prices, bins=bins, weights=volumes)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    total = vol_hist.sum()
    return pd.DataFrame({
        'price_level': bin_centers,
        'volume': vol_hist,
        'pct': vol_hist / total if total > 0 else 0
    })


# ═══════════════════════════════════════════════════
# Risk Management  
# ═══════════════════════════════════════════════════

def kelly_fraction(win_prob: float, risk_reward: float = 2.0) -> float:
    """
    Kelly Criterion — Optimal position sizing.
    
    Args:
        win_prob: Probability of winning (0-1)
        risk_reward: Risk/Reward ratio (e.g. 2.0 = 2:1)
    
    Returns: Fraction of bankroll to risk (0-1)
    """
    q = 1 - win_prob
    return max(0.0, (win_prob * risk_reward - q) / risk_reward)


def atr_stop_levels(df: pd.DataFrame, atr_period: int = 14,
                    sl_mult: float = 1.5, tp_mult: float = 3.0) -> dict:
    """ATR-based stop loss and take profit levels."""
    atr_val = atr(df, atr_period).iloc[-1]
    last_close = df['close'].iloc[-1]
    return {
        'stop_loss': last_close - (atr_val * sl_mult),
        'take_profit': last_close + (atr_val * tp_mult),
        'atr': atr_val
    }
