#!/usr/bin/env python3
"""
core/config.py — Centralized Configuration Loader
Loads settings.yaml + .env into a structured Settings object.
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from dotenv import load_dotenv

# ── Load .env ────────────────────────────────────────────────────
load_dotenv()

# ── Token / Chat Constants ───────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")
TOPIC_ID = os.getenv("TOPIC_ID", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")


@dataclass
class TickerConfig:
    symbol: str                   # e.g. "BTC/USDT:USDT"
    spot: str                     # e.g. "BTC/USDT"
    name: str                     # e.g. "Bitcoin"
    circulating_supply: int       # Approximate circulating supply


@dataclass
class ExchangeConfig:
    id: str = "binance"
    type: str = "swap"
    rate_limit: bool = True
    timeout: int = 30000


@dataclass
class ThresholdsConfig:
    zscore_overvalued: float = 2.0
    zscore_undervalued: float = -2.0
    absorption_z_threshold: float = 2.0
    kelly_risk_reward: float = 2.0
    significant_delta_std: float = 1.5
    fractal_window: int = 5
    heatmap_bins: int = 50
    heatmap_smooth_sigma: int = 3


@dataclass
class SchedulerConfig:
    orderflow_hours: int = 4
    spotdiff_hours: int = 1
    zscore_hours: int = 24
    heatmap_hours: int = 4


@dataclass
class ThemeConfig:
    bg: str = "#0b0e11"
    bull: str = "#00C853"
    bear: str = "#ff4444"
    neutral: str = "white"
    accent: str = "gold"
    text: str = "white"
    grid: str = "#2a2d33"


@dataclass 
class Settings:
    universe: List[TickerConfig] = field(default_factory=list)
    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)
    timeframes: Dict = field(default_factory=dict)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    theme: ThemeConfig = field(default_factory=ThemeConfig)

    # Computed
    telegram_token: str = ""
    chat_id: str = ""
    topic_id: str = ""

    def get_ticker(self, query: str) -> Optional[TickerConfig]:
        """Find ticker by symbol fragment (e.g. 'BTC', 'ETH', 'TAO')."""
        q = query.upper().strip()
        for t in self.universe:
            if q in t.symbol.upper() or q in t.name.upper():
                return t
        return None

    def get_all_symbols(self) -> List[str]:
        """Return list of all future symbols."""
        return [t.symbol for t in self.universe]

    @property
    def default_ticker(self) -> TickerConfig:
        """First ticker in universe (BTC)."""
        return self.universe[0] if self.universe else TickerConfig(
            symbol="BTC/USDT:USDT", spot="BTC/USDT",
            name="Bitcoin", circulating_supply=19800000
        )


def _load_settings() -> Settings:
    """Load and parse settings.yaml + .env credentials."""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    config_path = os.path.abspath(config_path)

    raw = {}
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            raw = yaml.safe_load(f) or {}

    # Parse universe
    universe = []
    for item in raw.get('universe', []):
        universe.append(TickerConfig(
            symbol=item.get('symbol', ''),
            spot=item.get('spot', ''),
            name=item.get('name', ''),
            circulating_supply=item.get('circulating_supply', 0)
        ))

    # Parse exchange
    ex_raw = raw.get('exchange', {})
    exchange = ExchangeConfig(
        id=ex_raw.get('id', 'binance'),
        type=ex_raw.get('type', 'swap'),
        rate_limit=ex_raw.get('rate_limit', True),
        timeout=ex_raw.get('timeout', 30000)
    )

    # Thresholds
    th_raw = raw.get('thresholds', {})
    thresholds = ThresholdsConfig(**{k: v for k, v in th_raw.items() if hasattr(ThresholdsConfig, k)})

    # Scheduler
    sc_raw = raw.get('scheduler', {})
    scheduler = SchedulerConfig(**{k: v for k, v in sc_raw.items() if hasattr(SchedulerConfig, k)})

    # Theme
    tm_raw = raw.get('theme', {})
    theme = ThemeConfig(**{k: v for k, v in tm_raw.items() if hasattr(ThemeConfig, k)})

    return Settings(
        universe=universe,
        exchange=exchange,
        timeframes=raw.get('timeframes', {}),
        thresholds=thresholds,
        scheduler=scheduler,
        theme=theme,
        telegram_token=TELEGRAM_TOKEN,
        chat_id=CHAT_ID,
        topic_id=TOPIC_ID
    )


# ── Singleton ────────────────────────────────────────────────────
settings = _load_settings()
