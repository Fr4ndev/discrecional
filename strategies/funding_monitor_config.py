#!/usr/bin/env python3
"""
strategies/funding_monitor_config.py — Funding Monitor Configuration
═══════════════════════════════════════════════════════════════════════
Dataclass config for the multi-exchange Funding + OI + OBI monitor.
Loads from the `funding_monitor` section of config/settings.yaml.
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Dict, List
from pathlib import Path


# ──────────────────────────────────────────────────────────────────
# Symbol Mapping per Exchange (CCXT unified format)
# ──────────────────────────────────────────────────────────────────
DEFAULT_EXCHANGE_SYMBOLS: Dict[str, Dict[str, str]] = {
    "binanceusdm": {
        "BTC": "BTC/USDT:USDT",
        "ETH": "ETH/USDT:USDT",
    },
    "bybit": {
        "BTC": "BTC/USDT:USDT",
        "ETH": "ETH/USDT:USDT",
    },
    "okx": {
        "BTC": "BTC/USDT:USDT",
        "ETH": "ETH/USDT:USDT",
    },
    "hyperliquid": {
        "BTC": "BTC/USDT:USDT",
        "ETH": "ETH/USDT:USDT",
    },
}


@dataclass
class MonitorThresholds:
    """Thresholds validated by literature (He, Zhang, Giagkiozis, Bieganowski)."""
    # Funding Rate absolute threshold (%) — He [1], Zhang [4]
    funding_abs: float = 0.01
    # ΔFunding 1h threshold (%) — Ackerer [2]
    delta_funding_1h: float = 0.005
    # ΔOI 1h threshold (%) — Giagkiozis [6]
    delta_oi_1h: float = 15.0
    # ΔOI 30m threshold (%)
    delta_oi_30m: float = 10.0
    # |OBI| threshold — Bieganowski [7]
    obi_abs: float = 0.40
    # Sensible mode thresholds
    sensible_delta_oi: float = 5.0
    sensible_obi: float = 0.40
    # Conservative mode thresholds
    conservative_funding_abs: float = 0.01
    conservative_delta_funding: float = 0.005
    conservative_delta_oi: float = 10.0
    conservative_obi: float = 0.45


@dataclass
class FundingMonitorConfig:
    """Complete configuration for the Funding + OI + OBI monitor."""
    # Exchanges to monitor
    exchanges: List[str] = field(default_factory=lambda: [
        "binanceusdm", "bybit", "okx", "hyperliquid"
    ])
    # Assets to track
    assets: List[str] = field(default_factory=lambda: ["BTC", "ETH"])
    # Symbol mappings per exchange
    exchange_symbols: Dict[str, Dict[str, str]] = field(
        default_factory=lambda: DEFAULT_EXCHANGE_SYMBOLS.copy()
    )
    # Polling interval (seconds) — balanced for rate limit safety
    poll_interval_seconds: int = 12
    # Order book depth for OBI calculation
    orderbook_depth: int = 50
    # Trigger mode: "sensible" or "conservative"
    trigger_mode: str = "sensible"
    # Thresholds
    thresholds: MonitorThresholds = field(default_factory=MonitorThresholds)
    # Reports output directory
    reports_dir: str = "./reports"
    # Rolling window sizes (number of samples)
    rolling_window_1h: int = 300  # ~1h at 12s intervals
    rolling_window_30m: int = 150  # ~30m at 12s intervals
    # Max retries per exchange per cycle
    max_retries: int = 3
    # Base retry delay (seconds)
    retry_base_delay: float = 2.0


def load_monitor_config() -> FundingMonitorConfig:
    """Load monitor config from settings.yaml `funding_monitor` section."""
    config_path = Path(__file__).parent.parent / "config" / "settings.yaml"

    raw = {}
    if config_path.exists():
        with open(config_path, "r") as f:
            raw = yaml.safe_load(f) or {}

    fm_raw = raw.get("funding_monitor", {})
    if not fm_raw:
        return FundingMonitorConfig()

    # Parse thresholds
    th_raw = fm_raw.get("thresholds", {})
    thresholds = MonitorThresholds(
        **{k: v for k, v in th_raw.items() if hasattr(MonitorThresholds, k)}
    )

    # Parse exchange symbols
    ex_sym_raw = fm_raw.get("exchange_symbols", {})
    exchange_symbols = DEFAULT_EXCHANGE_SYMBOLS.copy()
    if ex_sym_raw:
        exchange_symbols.update(ex_sym_raw)

    default_cfg = FundingMonitorConfig()
    return FundingMonitorConfig(
        exchanges=fm_raw.get("exchanges", default_cfg.exchanges),
        assets=fm_raw.get("assets", default_cfg.assets),
        exchange_symbols=exchange_symbols,
        poll_interval_seconds=fm_raw.get("poll_interval_seconds", 12),
        orderbook_depth=fm_raw.get("orderbook_depth", 50),
        trigger_mode=fm_raw.get("trigger_mode", "sensible"),
        thresholds=thresholds,
        reports_dir=fm_raw.get("reports_dir", "./reports"),
        rolling_window_1h=fm_raw.get("rolling_window_1h", 300),
        rolling_window_30m=fm_raw.get("rolling_window_30m", 150),
        max_retries=fm_raw.get("max_retries", 3),
        retry_base_delay=fm_raw.get("retry_base_delay", 2.0),
    )
