#!/usr/bin/env python3
"""
daemons/Guardian_Daemon.py — Unified Senior Desk Guardian v1.0
═══════════════════════════════════════════════════════════════════════════
Single persistent process that replaces 6 independent daemons:
  rotation_sentinel.py  → IgnitionBridgeTask
  ignition_daemon.py    → IgnitionBridgeTask (merged)
  squeeze_watcher.py    → SqueezeMonitorTask
  spoof_daemon.py       → SpoofDetectorTask
  volume_daemon.py      → VolumeMonitorTask
  opportunity_sentinel.py → OpportunityTask

ARCHITECTURE:
  - GuardianDaemon: asyncio task supervisor with auto-restart
  - SentinelGateway: centralized Telegram dispatcher (rate-limited, deduped)
  - Shared IntelligenceHub singleton — ONE exchange connection for all tasks
  - LiquidityAwareStopLoss integrated into IgnitionBridgeTask

GOLDEN RULES (preserved, DO NOT TOUCH):
  VPIN_THRESHOLD      = 0.62    (informed flow gate)
  BASIS_THRESHOLD_PCT = -0.05%  (spot premium / accumulation)
  CVD_ACCEL_GATE      = 0.0     (aggression must be positive)
  OBI_IGNITION        = 0.40    (BTC+ETH coordinated threshold)

Usage:
    python3 -u daemons/Guardian_Daemon.py

    # Disable specific sentinels at runtime:
    DISABLE_SQUEEZE=1 DISABLE_VOLUME=1 python3 daemons/Guardian_Daemon.py

    # Dry-run (no Telegram, no execution):
    DRY_RUN=1 python3 daemons/Guardian_Daemon.py
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
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Coroutine, Dict, List, Optional

import httpx
import requests

import os
import sys
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.config import settings
from core.Core_Intelligence_Hub import (
    IntelligenceHub,
    VPIN_THRESHOLD,
    BASIS_THRESHOLD_PCT,
    CVD_ACCEL_GATE,
    OBI_IGNITION,
    MarketSnapshot,
)
from core.execution_engine import ExecutionEngine, LiquidityAwareStopLoss
from daemons.base import BaseSentinelTask
from daemons.sfp_advanced_monitor import SFPAdvancedMonitor
from daemons.ict_v16_sentinel import ICTAlphaV16Task
from alerts.gateway import SentinelGateway, AlertMessage
from core.bus import SignalBus, Signal
from senior_audit_orchestrator import SeniorAuditOrchestrator
from core.ai_analyst import get_analyst

# ── Paths ─────────────────────────────────────────────────────────
DATA_DIR   = Path("/home/wek/Escritorio/ccxtv2/data")
LOG_FILE   = DATA_DIR / "guardian_daemon.log"
HBEAT_FILE = DATA_DIR / "guardian_hbeat.json"
KILL_SWITCH = DATA_DIR / "STOP_ALL.lock"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DRY_RUN = os.getenv("DRY_RUN", "0") == "1"

# ── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [GUARDIAN] %(levelname)-8s %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE)),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("GuardianDaemon")


# ═══════════════════════════════════════════════════════════════════
# SENTINEL GATEWAY — Extracted to alerts/gateway.py
# SentinelGateway + AlertMessage imported at top of file.
# ═══════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════
# TASK 1: IGNITION BRIDGE (BTC → ETH Rotation + Ignition Monitor)
# Merges: rotation_sentinel.py + ignition_daemon.py
# ═══════════════════════════════════════════════════════════════════

class IgnitionBridgeTask(BaseSentinelTask):
    """
    Monitors the full Ignition Bridge protocol (Section 6, FLOWS_OPERATING_MANUAL).

    States:
      STEALTH_PHASE           → ETH OBI ready, BTC still noisy → MONITOR ONLY
      ALPHA_ROTATION_TRIGGERED → BTC consolidating + ETH primed → EXECUTE
      BTC_RESURGENCE          → BTC re-igniting (Tox > 0.70) → PAUSE ETH entry
      NEUTRAL                 → No signal

    GOLDEN RULES PRESERVED:
      VPIN > 0.62, Basis < -0.05%, CVD'' > 0
    """

    name          = "IgnitionBridge"
    poll_interval = 30.0
    enabled_env_var = "DISABLE_IGNITION"

    BTC_SYM = "BTC/USDT:USDT"
    ETH_SYM = "ETH/USDT:USDT"
    EXECUTION_SIZE_USD = 50_000

    def __init__(self, hub: IntelligenceHub, gateway: SentinelGateway):
        super().__init__(hub, gateway)
        self.execution = ExecutionEngine()
        self._last_trigger_ts = 0.0
        self._trigger_cooldown = 3600   # 1h between executions
        self._prev_phase = "NEUTRAL"

    async def _cycle(self) -> None:
        state = await self.hub.ignition_check(self.BTC_SYM, self.ETH_SYM)
        phase = state["phase"]
        btc   = state["btc"]
        eth   = state["eth"]

        # ── HIGH CONVICTION ONLY ───────────────────────────────────
        # Silencing noisy neutral/stealth phases unless they transition to Ignition.
        
        if phase == "ALPHA_ROTATION_TRIGGERED":
            cooldown_ok = (time.time() - self._last_trigger_ts) > self._trigger_cooldown
            if cooldown_ok:
                await self._execute_rotation(eth)
                self._last_trigger_ts = time.time()

        elif phase == "BTC_RESURGENCE":
            # Only alert if it's a critical resurgence
            await self.alert(
                f"⚠️ *BTC RESURGENCE — ROTATION PAUSED*\n"
                f"🔥 BTC VPIN: `{btc['vpin']:.2f}` (Re-ignition)\n"
                f"⚓ ETH entry held.",
                priority=2,
                dedup_key="btc_resurgence",
                symbol=self.BTC_SYM
            )

        self._prev_phase = phase

    async def _execute_rotation(self, eth: dict) -> None:
        """Execute the BTC→ETH Alpha Rotation with full institutional guard."""
        self.log.info("🔥 ALPHA ROTATION TRIGGERED — Initiating execution protocol.")

        # 1. Build LiquidityAwareStopLoss
        eth_price = await self.hub.get_price(self.ETH_SYM)
        sl_guard = LiquidityAwareStopLoss(
            entry_price=eth_price,
            symbol=self.ETH_SYM,
            tox_index=eth["vpin"],
            slippage_real=0.00015,
        )
        await sl_guard.initialize()

        # 2. Predatory execution (TWAP if slippage high)
        if not DRY_RUN:
            await self.execution.predatory_execute(
                self.ETH_SYM, "buy", self.EXECUTION_SIZE_USD
            )

        # 3. Send institutional alert
        basis_pct  = eth.get("basis_pct", 0)
        cvd_accel  = eth.get("cvd_accel", 0)
        vpin       = eth["vpin"]

        await self.alert(
            f"🚨 *ALPHA ROTATION EXECUTED: BTC → ETH*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔥 *ETH VPIN:* `{vpin:.2f}` (Gate: >{VPIN_THRESHOLD})\n"
            f"💎 *ETH Basis:* `{basis_pct}%` (Spot Premium ✅)\n"
            f"📈 *CVD Acceleration:* `{cvd_accel:.4f}` (Aggression ✅)\n"
            f"🛡️ *UDC Floor SL:* `${sl_guard.sl_price:,.2f}`\n"
            f"💰 *Size:* `${self.EXECUTION_SIZE_USD:,.0f}` USD\n"
            f"🦈 *Sniper Status:* {'EXECUTED (MARKET)' if not DRY_RUN else 'DRY_RUN'}",
            priority=1,
            dedup_key="alpha_rotation",
        )

        self.log.info(f"✅ Rotation complete. SL @ ${sl_guard.sl_price:,.2f}")


# ═══════════════════════════════════════════════════════════════════
# TASK 2: SQUEEZE MONITOR
# Merges: squeeze_watcher.py
# ═══════════════════════════════════════════════════════════════════

class SqueezeMonitorTask(BaseSentinelTask):
    """
    ETH Short Squeeze detector.

    Conditions for HIGH CONVICTION (3/3):
      1. Funding Rate < -0.005%  (shorts paying excessively)
      2. OBI > +0.20             (active bid absorption)
      3. CVD ratio > 1.40        (buyers are the aggressor)

    2/3 conditions → WARNING alert.
    """

    name          = "SqueezeMonitor"
    poll_interval = 20.0
    enabled_env_var = "DISABLE_SQUEEZE"

    PERP_SYM       = "ETH/USDT:USDT"
    FUNDING_THRESH = -0.005
    OBI_THRESH     = 0.20
    CVD_THRESH     = 1.40
    COOLDOWN_HC    = 1800    # 30 min
    COOLDOWN_WARN  = 600

    def __init__(self, hub: IntelligenceHub, gateway: SentinelGateway):
        super().__init__(hub, gateway)
        self._last_hc   = 0.0
        self._last_warn = 0.0
        self._funding_cache: Optional[float] = None
        self._funding_cycle = 0

    async def _cycle(self) -> None:
        # Funding rate — refresh every 5 cycles (~100s)
        if self._funding_cycle == 0 or self._funding_cache is None:
            fund_state = await self.hub.get_funding_state(self.PERP_SYM)
            if fund_state:
                self._funding_cache = fund_state.rate_pct
                self.log.info(f"💰 Funding updated: {self._funding_cache:.4f}%")
        self._funding_cycle = (self._funding_cycle + 1) % 5

        # OBI, CVD, price — parallel
        obi_snap, cvd_state, price = await asyncio.gather(
            self.hub.get_obi(self.PERP_SYM, 50),
            self.hub.get_cvd_state(self.PERP_SYM, 200),
            self.hub.get_price(self.PERP_SYM),
        )

        obi = obi_snap.obi
        cvd_ratio = 1.0
        if cvd_state:
            # Infer buy/sell ratio from velocity direction
            cvd_ratio = max(0.1, 1.0 + cvd_state.velocity / max(abs(cvd_state.velocity), 1))

        score, reasons = self._score(self._funding_cache, obi, cvd_ratio)
        self.log.info(
            f"Score={score}/3 | Funding={self._funding_cache or 0:.4f}% | "
            f"OBI={obi:+.3f} | CVD={cvd_ratio:.2f} | ${price:,.2f}"
        )

        now = time.time()

        if score == 3 and (now - self._last_hc) > self.COOLDOWN_HC:
            ann = (self._funding_cache or 0) * 3 * 365 * 100
            await self.alert(
                f"🚨 *ETH SHORT SQUEEZE — ALTA CONVICCIÓN*\n"
                f"✅ Funding: `{(self._funding_cache or 0):.4f}%` (anual `{ann:.1f}%`)\n"
                f"✅ OBI D50: `{obi:+.3f}` (absorción comprobada)\n"
                f"✅ CVD ratio: `{cvd_ratio:.2f}` (compradores dominan)\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📍 Precio ETH: `${price:,.2f}`\n"
                f"🎯 Entry Scalp: `${price - price*0.001:,.2f}` – `${price:,.2f}`\n"
                f"💰 TP1: `${price*1.005:,.2f}` | TP2: `${price*1.012:,.2f}`\n"
                f"🛡️ SL: `${price*0.993:,.2f}`",
                priority=1,
                dedup_key="squeeze_hc",
                symbol=self.PERP_SYM
            )
            self._last_hc = now

        elif score == 2 and (now - self._last_warn) > self.COOLDOWN_WARN:
            await self.alert(
                f"⚠️ *ETH SQUEEZE WARNING ({score}/3 condiciones)*\n"
                + "\n".join(f"  ✅ {r}" for r in reasons) +
                f"\n📍 Precio: `${price:,.2f}`\n"
                f"💡 Vigilar — falta 1 condición para HC",
                priority=3,
                dedup_key="squeeze_warn",
                symbol=self.PERP_SYM
            )
            self._last_warn = now

    def _score(self, funding: Optional[float], obi: float,
               cvd_ratio: float) -> tuple:
        score = 0
        reasons = []
        if funding is not None and funding < self.FUNDING_THRESH:
            score += 1
            reasons.append(f"Funding `{funding:.4f}%` (shorts saturados)")
        if obi > self.OBI_THRESH:
            score += 1
            reasons.append(f"OBI `+{obi:.3f}` (absorción activa)")
        if cvd_ratio > self.CVD_THRESH:
            score += 1
            reasons.append(f"CVD ratio `{cvd_ratio:.2f}` (compradores aggressor)")
        return score, reasons


# ═══════════════════════════════════════════════════════════════════
# TASK 3: SPOOF DETECTOR
# Merges: spoof_daemon.py
# ═══════════════════════════════════════════════════════════════════

class SpoofDetectorTask(BaseSentinelTask):
    """
    Anti-Spoofing OBI Snap Sentinel.
    Detects rapid OBI changes (>SNAP_THRESHOLD in 30s) = liquidity pulling.
    Covers full universe from settings.universe.
    """

    name          = "SpoofDetector"
    poll_interval = 15.0  # Faster polling for better fusion
    enabled_env_var = "DISABLE_SPOOF"

    SNAP_THRESHOLD = 0.35
    HISTORY_LEN    = 5
    OB_DEPTH       = 50

    def __init__(self, hub: IntelligenceHub, gateway: SentinelGateway):
        super().__init__(hub, gateway)
        self._obi_history: Dict[str, deque] = {
            t.symbol: deque(maxlen=self.HISTORY_LEN)
            for t in getattr(settings, "universe", [])
        }

    async def _cycle(self) -> None:
        for ticker in getattr(settings, "universe", []):
            sym = ticker.symbol
            try:
                ob = await self.hub.get_order_book(sym, self.OB_DEPTH)
                if not ob:
                    continue
                bids = sum(b[1] for b in ob.get("bids", []))
                asks = sum(a[1] for a in ob.get("asks", []))
                total = bids + asks
                obi = (bids - asks) / total if total > 0 else 0.0

                hist = self._obi_history.setdefault(sym, deque(maxlen=self.HISTORY_LEN))
                if hist:
                    delta = abs(obi - hist[-1])
                    if delta > self.SNAP_THRESHOLD:
                        # ── SIGNAL BUS: Publish for Fusion ──
                        SignalBus.instance().publish(Signal(
                            kind="SPOOF",
                            source=self.name,
                            asset=sym,
                            confidence=0.8,
                            payload={"value": delta, "prev_obi": hist[-1], "curr_obi": obi}
                        ))

                        await self.alert(
                            f"🚨 *SPOOFING DETECTED: {ticker.name}*\n"
                            f"📊 OBI Snap: `{hist[-1]:+.4f}` → `{obi:+.4f}`\n"
                            f"⚡ Delta: `{delta:.4f}`\n"
                            f"⚠️ Liquiditiy Pulling detected.",
                            priority=2,
                            dedup_key=f"spoof_{sym}_{int(time.time()/60)}",
                            symbol=sym
                        )

                hist.append(obi)
                await asyncio.sleep(0.15)  # stagger API calls

            except Exception as e:
                self.log.error(f"Spoof error {sym}: {e}")


# ═══════════════════════════════════════════════════════════════════
# TASK 4: VOLUME MONITOR
# Merges: volume_daemon.py
# ═══════════════════════════════════════════════════════════════════

class VolumeMonitorTask(BaseSentinelTask):
    """
    Real-time Volume & CVD Pulse Monitor.
    Classifies buy/sell pressure per symbol in the universe.
    """

    name          = "VolumeMonitor"
    poll_interval = 60.0
    enabled_env_var = "DISABLE_VOLUME"

    TRADE_LIMIT = 500

    async def _cycle(self) -> None:
        for ticker in getattr(settings, "universe", []):
            sym = ticker.symbol
            try:
                trades = await self.hub.get_trades(sym, self.TRADE_LIMIT)
                if trades is None or trades.empty:
                    continue

                buy_vol  = trades[trades["side"] == "buy"]["amount"].sum()
                sell_vol = trades[trades["side"] == "sell"]["amount"].sum()
                ratio    = (buy_vol / sell_vol) if sell_vol > 0 else 999.0

                if buy_vol > sell_vol * 1.5:
                    verdict = "💎 BULLISH CONVICTION"
                elif sell_vol > buy_vol * 1.5:
                    verdict = "⚠️ BEARISH DISTRIBUTION"
                else:
                    verdict = "⚖️ NEUTRAL EQUILIBRIUM"

                self.log.info(
                    f"{ticker.name} | Buys:{buy_vol:.2f} Sells:{sell_vol:.2f} "
                    f"Ratio:{ratio:.2f} | {verdict}"
                )
                await asyncio.sleep(0.5)
            except Exception as e:
                self.log.error(f"Volume error {sym}: {e}")


# ═══════════════════════════════════════════════════════════════════
# TASK 5: OPPORTUNITY SENTINEL
# Merges: opportunity_sentinel.py
# ═══════════════════════════════════════════════════════════════════

@dataclass
class _AssetOpState:
    name:       str
    last_obi:   float = 0.0
    last_cvd:   float = 1.0
    last_alert: Dict[str, float] = field(default_factory=dict)

    OBI_FLIP_THRESHOLD = 0.30
    COOLDOWN           = 600

    def cooled_down(self, kind: str) -> bool:
        return (time.time() - self.last_alert.get(kind, 0)) > self.COOLDOWN

    def mark(self, kind: str) -> None:
        self.last_alert[kind] = time.time()


# ═══════════════════════════════════════════════════════════════════
# TASK 5: OPPORTUNITY SENTINEL (Senior Intelligence Module)
# ═══════════════════════════════════════════════════════════════════

class OpportunityTask(BaseSentinelTask):
    """
    Senior Intelligence Module v2.0.
    - Combines OBI/CVD flips with real-time level proximity.
    - Integrates AbsorptionDetector for toxicity and iceberg context.
    - Produces high-conviction Scalp/Intraday/Swing verdicts.
    """

    name          = "SeniorIntelligence"
    poll_interval = 15.0
    enabled_env_var = "DISABLE_OPPORTUNITY"

    ASSETS = [
        {"perp": "BTC/USDT:USDT", "spot": "BTC/USDT", "name": "BTC"},
        {"perp": "ETH/USDT:USDT", "spot": "ETH/USDT", "name": "ETH"},
    ]
    
    LEVELS_FILE = DATA_DIR / "watchlist_levels.json"

    def __init__(self, hub: IntelligenceHub, gateway: SentinelGateway):
        super().__init__(hub, gateway)
        from funding_action_server.actions.absorption_detector import AbsorptionDetector
        self.detector = AbsorptionDetector(hub)
        self._states = {a["perp"]: _AssetOpState(name=a["name"]) for a in self.ASSETS}
        self._levels = {}

    def _load_levels(self):
        try:
            if self.LEVELS_FILE.exists():
                with open(self.LEVELS_FILE) as f:
                    self._levels = json.load(f)
        except Exception as e:
            self.log.error(f"Error loading levels: {e}")

    async def _cycle(self) -> None:
        self._load_levels()
        await asyncio.gather(*[self._scan_asset(a) for a in self.ASSETS])

    async def _scan_asset(self, asset: dict) -> None:
        perp  = asset["perp"]
        name  = asset["name"]
        state = self._states[perp]

        # 1. Advanced Metrics via Detector
        try:
            abs_res = await self.detector.scan(perp)
        except Exception as e:
            self.log.error(f"Detector error {perp}: {e}")
            return

        price = abs_res.price
        obi = abs_res.details.get("obi_current", 0.0)
        cvd_ratio = 1.0
        cvd_usd = abs_res.details.get("cvd_usd", 0.0)
        
        # Approximate CVD Ratio for legacy logic
        if cvd_usd > 100_000: cvd_ratio = 1.5
        elif cvd_usd < -100_000: cvd_ratio = 0.6

        # 2. Check Proximity to Levels
        # PATCH-01: Guard against price=0 (ticker fetch failure → ZeroDivisionError)
        if price == 0:
            self.log.debug(f"[{name}] Price unavailable, skipping level proximity check")
            state.last_obi = obi
            state.last_cvd = cvd_ratio
            self.log.debug(f"[{name}] OBI={obi:+.3f} CVD={cvd_usd:.0f} $N/A")
            return
        proximity_context = ""
        is_near_level = False
        asset_levels = self._levels.get(perp, {})
        
        for sup in asset_levels.get("supports", []):
            if 0 < (price - sup) / price < 0.002: # Within 0.2% of support
                proximity_context = f"📍 Price near Support: `${sup:,.2f}`"
                is_near_level = True
                break
        
        for res in asset_levels.get("resistances", []):
            if 0 < (res - price) / price < 0.002: # Within 0.2% of resistance
                proximity_context = f"📍 Price near Resistance: `${res:,.2f}`"
                is_near_level = True
                break

        # 3. Decision Logic: High Conviction Flip
        prev_obi = state.last_obi
        OBI_TH = _AssetOpState.OBI_FLIP_THRESHOLD + 0.10 # Tightened threshold
        
        # Bullish Flip Signal (Requires FUSION or Level Proximity)
        if prev_obi < -0.10 and obi > OBI_TH and state.cooled_down("senior_bull"):
            bus = SignalBus.instance()
            recent_spoof = bus.get_recent(type="SPOOF", asset=name, window=20)
            
            if recent_spoof or is_near_level:
                verdict = "⚔️ FUSION: BULLISH IGNITION" if recent_spoof else "HIGH CONVICTION LONG"
                fusion_text = f"\n🔥 *CONFLUENCE:* Spoofing detected {int(time.time()-recent_spoof.timestamp)}s ago." if recent_spoof else ""

                await self.alert(
                    f"🏛️ *Senior Verdict: [{verdict}]*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🪙 Asset: *{name}* | `${price:,.2f}`\n"
                    f"{proximity_context}{fusion_text}\n\n"
                    f"🎯 *Core Signals:*\n"
                    f"- 🔄 OBI Flip: `{prev_obi:+.2f}` → `{obi:+.2f}`\n"
                    f"- 🌊 CVD Net: `{cvd_usd/1000:+.0f}k USD`",
                    priority=2, dedup_key=f"senior_bull_{name}",
                    symbol=perp
                )
                state.mark("senior_bull")

        # Bearish Flip Signal
        if prev_obi > 0.10 and obi < -OBI_TH and state.cooled_down("senior_bear"):
            bus = SignalBus.instance()
            recent_spoof = bus.get_recent(type="SPOOF", asset=name, window=20)
            
            if recent_spoof or is_near_level:
                verdict = "⚔️ FUSION: BEARISH LIQUIDATION" if recent_spoof else "HIGH CONVICTION SHORT"
                fusion_text = f"\n🔥 *CONFLUENCE:* Spoofing detected {int(time.time()-recent_spoof.timestamp)}s ago." if recent_spoof else ""

                await self.alert(
                    f"🏛️ *Senior Verdict: [{verdict}]*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🪙 Asset: *{name}* | `${price:,.2f}`\n"
                    f"{proximity_context}{fusion_text}\n\n"
                    f"🎯 *Core Signals:*\n"
                    f"- 🔄 OBI Flip: `{prev_obi:+.2f}` → `{obi:+.2f}`\n"
                    f"- 🌊 CVD Net: `{cvd_usd/1000:+.0f}k USD`",
                    priority=2, dedup_key=f"senior_bear_{name}",
                    symbol=perp
                )
                state.mark("senior_bear")

        state.last_obi = obi
        state.last_cvd = cvd_ratio
        self.log.debug(f"[{name}] OBI={obi:+.3f} CVD={cvd_usd:.0f} ${price:.2f}")



# ═══════════════════════════════════════════════════════════════════
# TASK 6: WHALE MONITOR
# Merges: whale_sentinel.py
# ═══════════════════════════════════════════════════════════════════

class WhaleMonitorTask(BaseSentinelTask):
    """
    Whale & Flow Monitor v3.0 (Institutional Grade).
    - Fixed Windows: Non-overlapping 30s blocks to prevent signal recycling.
    - Two-Tier Labels: 'LARGE' vs 'WHALE' based on liquidity-adjusted thresholds.
    - Regime Filter: Prevents flip-flops unless volume is 3x the threshold.
    - Full Context: Includes execution Price and OBI at signal time.
    """

    name          = "WhaleMonitor"
    poll_interval = 10.0  # Poll faster to catch block completions
    enabled_env_var = "DISABLE_WHALE"

    # Institutional Thresholds (Whale level)
    WHALE_THRESHOLDS = {
        "BTC/USDT:USDT": 750_000,
        "ETH/USDT:USDT": 1_100_000,
        "SOL/USDT:USDT": 800_000,
        "LINK/USDT:USDT": 150_000,
        "HYPE/USDT:USDT": 250_000,
        "TAO/USDT:USDT": 200_000,
    }
    LARGE_FACTOR = 0.33  # Large = 33% of Whale threshold
    WINDOW_SECONDS = 30
    REGIME_COOLDOWN = 60

    def __init__(self, hub: IntelligenceHub, gateway: SentinelGateway):
        super().__init__(hub, gateway)
        self._last_trade_ts: Dict[str, float] = {}
        self._current_block_id: Dict[str, int] = {}
        self._block_data: Dict[str, Dict] = {} # {sym: {block_id: {buys, sells, trades}}}
        self._last_alert: Dict[str, Dict] = {} # {sym: {side, time, vol}}

    async def _cycle(self) -> None:
        now = time.time()
        for ticker in getattr(settings, "universe", []):
            sym = ticker.symbol
            try:
                trades = await self.hub.get_trades(sym, limit=200)
                if trades is None or trades.empty: continue

                # 1. Block-based Aggregation (Fixed Windows)
                for _, row in trades.iterrows():
                    ts = float(row["timestamp"])
                    block_id = int(ts / (self.WINDOW_SECONDS * 1000))
                    
                    if sym not in self._current_block_id:
                        self._current_block_id[sym] = block_id

                    # If block finished, process it
                    if block_id > self._current_block_id[sym]:
                        await self._process_completed_block(sym, ticker.name, self._current_block_id[sym])
                        self._current_block_id[sym] = block_id

                    # Accumulate in current block
                    self._block_data.setdefault(sym, {}).setdefault(block_id, {"buys": 0.0, "sells": 0.0, "count": 0})
                    amt_usd = float(row["amount"]) * float(row["price"])
                    if str(row["side"]).lower() == "buy":
                        self._block_data[sym][block_id]["buys"] += amt_usd
                    else:
                        self._block_data[sym][block_id]["sells"] += amt_usd
                    self._block_data[sym][block_id]["count"] += 1

                self._last_trade_ts[sym] = float(trades["timestamp"].iloc[-1])

            except Exception as e:
                self.log.error(f"Whale error {sym}: {e}")

    async def _process_completed_block(self, sym: str, display_name: str, block_id: int) -> None:
        data = self._block_data.get(sym, {}).pop(block_id, None)
        if not data: return

        buys = data["buys"]
        sells = data["sells"]
        total = buys + sells
        net = buys - sells
        side = "ACCUMULATION" if net > 0 else "DISTRIBUTION"
        
        whale_th = self.WHALE_THRESHOLDS.get(sym, 200_000)
        large_th = whale_th * self.LARGE_FACTOR

        if total < large_th: return

        # 2. Anti-Flip-Flop Logic (Regime Filter)
        now = time.time()
        last = self._last_alert.get(sym)
        if last and last["side"] != side:
            elapsed = now - last["time"]
            if elapsed < self.REGIME_COOLDOWN and total < (last["vol"] * 2.5):
                self.log.info(f"Filtered Flip-Flop for {display_name}: {side} too soon.")
                return

        # 3. Labeling & Context
        label = "WHALE" if total >= whale_th else "LARGE"
        
        # ── NOISE FILTER & CURATION BRIDGE ──
        # Always send to Curation Buffer for Synthesis
        if label == "WHALE":
            try:
                # Local import to avoid circular dependency
                from daemons.Guardian_Daemon import dispatch_enriched_alert
                dispatch_enriched_alert(
                    self.gateway, self.gateway.curation_buffer,
                    "whale", sym, f"Whale {side}: {total/1e6:.1f}M USD",
                    core_hub=self.hub
                )
            except Exception as e:
                self.log.error(f"Curation ingestion failed: {e}")

        # Only alert DIRECTLY to Telegram if it's an exceptional move
        # (Otherwise the CurationBuffer handles the 'Alpha Pulse' synthesis)
        MIN_DIRECT_ALERT_USD = 5_000_000 if sym in ["BTC/USDT:USDT", "ETH/USDT:USDT"] else 1_000_000
        
        if total < MIN_DIRECT_ALERT_USD:
            self.log.debug(f"Whale flow {total/1e6:.1f}M < {MIN_DIRECT_ALERT_USD/1e6:.1f}M. Skipping direct alert.")
            return

        icon = "🐋" if net > 0 else "🩸"
        
        # Get real-time context from Hub
        snap = await self.hub.get_order_book(sym, limit=10)
        obi = 0.0
        price = 0.0
        if snap:
            price = (snap["bids"][0][0] + snap["asks"][0][0]) / 2
            b_vol = sum(b[1] for b in snap["bids"])
            a_vol = sum(a[1] for a in snap["asks"])
            obi = (b_vol - a_vol) / (b_vol + a_vol) if (b_vol + a_vol) > 0 else 0

        self._last_alert[sym] = {"side": side, "time": now, "vol": total}

        await self.alert(
            f"{icon} *INSTITUTIONAL {side} — {display_name}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *Net Flow:* `{net/1e6:+.2f}M USD`\n"
            f"📊 *Total Vol:* `{total/1e6:.2f}M USD`\n"
            f"📍 *Precio:* `${price:,.2f}`\n"
            f"⚖️ *OBI:* `{obi:+.3f}`\n"
            f"⏱ *Window:* `30s Fixed Block` (DIRECT)",
            priority=1, # Increased priority for direct alerts
            dedup_key=f"whale_v3_{sym}_{block_id}"
        )


# ═══════════════════════════════════════════════════════════════════
# TASK 7: SFP SENTINEL (Legacy Bridge)
# Merges: sfp_advanced_monitor.py
# ═══════════════════════════════════════════════════════════════════

class SFPSentinelTask(BaseSentinelTask):
    """
    SFP Advanced Monitor Wrapper.
    Runs the legacy SFP detection logic as a supervised Guardian task.
    """

    name          = "SFPSentinel"
    poll_interval = 10.0
    enabled_env_var = "DISABLE_SFP"

    def __init__(self, hub: IntelligenceHub, gateway: SentinelGateway):
        super().__init__(hub, gateway)
        self._monitor = SFPAdvancedMonitor(engine=hub, gateway=gateway)

    async def run(self) -> None:
        """Override base run to use SFP's internal loop."""
        if not self.is_enabled:
            self.log.info(f"{self.name} DISABLED by env var.")
            return

        self.log.info(f"🚀 {self.name} STARTED (supervised)")
        try:
            # We wrap the legacy run() which has its own loop.
            # Note: This still uses its own DataEngine for now.
            await self._monitor.run()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.log.error(f"SFPSentinel fatal error: {e}")
            raise

    async def _cycle(self) -> None:
        """Not used as we override run()."""
        pass


# ═══════════════════════════════════════════════════════════════════
# TASK 8: LEVEL BREAK MONITOR
# Merges: level_break_alert.py
# ═══════════════════════════════════════════════════════════════════

class LevelBreakTask(BaseSentinelTask):
    """
    Vigilancia de ruptura, retest y rechazo de niveles críticos.
    Poll agresivo (10s) para capturar SFP en tiempo real.
    """

    name          = "LevelBreak"
    poll_interval = 10.0
    enabled_env_var = "DISABLE_LEVELS"

    LEVELS_FILE = DATA_DIR / "watchlist_levels.json"
    PROX_PCT    = 0.002

    def __init__(self, hub: IntelligenceHub, gateway: SentinelGateway):
        super().__init__(hub, gateway)
        self._levels = {}
        self._last_state = {} # {sym: {price: "ABOVE/BELOW"}}
        self._last_alert = {} # {sym: {price: ts}}

    def _load_levels(self):
        try:
            if self.LEVELS_FILE.exists():
                with open(self.LEVELS_FILE) as f:
                    self._levels = json.load(f)
        except Exception as e:
            self.log.error(f"Error loading levels: {e}")

    async def _cycle(self) -> None:
        self._load_levels()
        for ticker in getattr(settings, "universe", []):
            sym = ticker.symbol
            asset_levels = self._levels.get(sym, {})
            if not asset_levels: continue

            price = await self.hub.get_price(sym)
            if price == 0: continue

            # Combine resistances and supports
            levels = [(float(l), "RESISTANCE") for l in asset_levels.get("resistances", [])]
            levels += [(float(l), "SUPPORT") for l in asset_levels.get("supports", [])]

            for val, kind in levels:
                state_key = f"{sym}_{val}"
                prev_state = self._last_state.get(state_key)
                curr_state = "ABOVE" if price > val else "BELOW"
                
                # Detect Breakout
                if prev_state and prev_state != curr_state:
                    direction = "UP" if curr_state == "ABOVE" else "DOWN"
                    await self.alert(
                        f"📍 *LEVEL BREAKOUT: {ticker.name}*\n"
                        f"🔑 Level: `${val:,.2f}` ({kind})\n"
                        f"🚀 Direction: `{direction}` | Price: `${price:,.2f}`\n"
                        f"📊 Status: Confirmed Break.",
                        priority=2,
                        dedup_key=f"break_{state_key}_{int(time.time()/600)}",
                        symbol=sym
                    )
                
                self._last_state[state_key] = curr_state

                # Detect Proximity/SFP (Simplified)
                if abs(price - val) / val < self.PROX_PCT:
                    # In a real SFP we'd check candle closes, but for proximity alert:
                    if (time.time() - self._last_alert.get(state_key, 0)) > 1200:
                        await self.alert(
                            f"👀 *LEVEL PROXIMITY: {ticker.name}*\n"
                            f"🔑 Level: `${val:,.2f}` ({kind})\n"
                            f"📍 Price: `${price:,.2f}`\n"
                            f"⚠️ Monitor for SFP / Rejection.",
                            priority=3,
                            dedup_key=f"prox_{state_key}",
                            symbol=sym
                        )
                        self._last_alert[state_key] = time.time()


# ═══════════════════════════════════════════════════════════════════
# TASK 9: STRATEGIC AUDIT (Z-Score + SpotDiff)
# ═══════════════════════════════════════════════════════════════════

class StrategicAuditTask(BaseSentinelTask):
    """
    Periodic HTF Audit (Elite Z-Score + SpotDiff).
    Updates macro intelligence every hour.
    """

    name          = "StrategicAudit"
    poll_interval = 3600.0  # 1 hour
    enabled_env_var = "DISABLE_STRATEGIC_AUDIT"

    async def _cycle(self) -> None:
        self.log.info("🎯 Initiating Strategic HTF Audit (Elite Z-Score)...")
        # Use subprocess to run the existing scripts to avoid re-implementing logic
        # and to keep them modular.
        for asset in ["BTC", "ETH"]:
            try:
                cmd = f"python3 strategies/zscore_chart.py {asset}"
                proc = await asyncio.create_subprocess_shell(
                    cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                await proc.wait()
                self.log.info(f"✅ Elite Z-Score for {asset} updated.")
            except Exception as e:
                self.log.error(f"Audit error {asset}: {e}")

        # Signal completion - Disabled redundant alert as SeniorAudit handles it better
        # await self.alert(...)
        self.log.info("🏛️ STRATEGIC HTF AUDIT COMPLETE")


# ═══════════════════════════════════════════════════════════════════
# TASK 10: SENIOR AUDIT REPORTING (PhD Synthesis)
# ═══════════════════════════════════════════════════════════════════

class SeniorAuditTask(BaseSentinelTask):
    """
    Automated Institutional Reporting Task.
    Runs the full orchestrator suite and uses DeepSeek to synthesize
    a high-conviction market report.
    """

    name          = "SeniorAudit"
    poll_interval = 3600.0  # Hourly full audit
    enabled_env_var = "DISABLE_AUDIT"

    async def _cycle(self) -> None:
        self.log.info("🧐 Starting Periodic Senior Institutional Audit...")
        
        try:
            # Execute auto_senior_analyst in full mode
            import subprocess
            proc = await asyncio.create_subprocess_exec(
                "python3", "auto_senior_analyst.py", "--mode", "full",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            out = stdout.decode('utf-8')
            
            verdict = "⚠️ Auto Senior Audit generated no visible output."
            if "============================================================" in out:
                parts = out.split("============================================================")
                if len(parts) >= 3:
                    verdict = parts[-2].strip()
            
            # 3. Dispatch to Telegram
            final_report = (
                f"🕵️ **SENIOR DESK | INSTITUTIONAL DOSSIER**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{verdict}\n\n"
                f"--- \n"
                f"📊 *Full technical audit archived in reports_history/*"
            )
            
            await self.alert(
                final_report[:4000],  # Telegram limit
                priority=2, # HIGH
                dedup_key=f"senior_audit_periodic_{int(time.time()/3600)}"
            )
            self.log.info("✅ Senior Audit dispatched to Telegram.")

        except Exception as e:
            self.log.error(f"Senior Audit Error: {e}")
            traceback.print_exc()

# ═══════════════════════════════════════════════════════════════════
# GUARDIAN DAEMON — Master Orchestrator
# ═══════════════════════════════════════════════════════════════════

class GuardianDaemon:
    """
    Process-level supervisor for all sentinel tasks.

    Lifecycle:
      1. Connect shared IntelligenceHub singleton
      2. Start SentinelGateway (Telegram dispatcher)
      3. Launch all tasks as asyncio.Tasks
      4. Supervise: restart crashed tasks after backoff
      5. Graceful shutdown on SIGINT/SIGTERM
    """

    TASK_RESTART_DELAY = 10.0    # seconds before restarting a crashed task
    HEARTBEAT_INTERVAL = 60      # cycles

    def __init__(self):
        self._hub: Optional[IntelligenceHub] = None
        self._gateway = SentinelGateway(dry_run=DRY_RUN)
        self._bus = SignalBus.instance()
        self._tasks: Dict[str, asyncio.Task] = {}
        self._sentinel_classes: List[type] = [
            IgnitionBridgeTask,
            SqueezeMonitorTask,
            # SpoofDetectorTask,
            # VolumeMonitorTask,
            # OpportunityTask,
            WhaleMonitorTask,
            # SFPSentinelTask,
            LevelBreakTask,
            StrategicAuditTask,
            SeniorAuditTask,
            # ICTAlphaV16Task,
        ]
        self._running = True
        self._cycle = 0

    async def run(self) -> None:
        logger.info("═" * 60)
        logger.info("🏛️  GUARDIAN DAEMON v1.0 — Senior Desk Intelligence")
        logger.info(f"   DRY_RUN: {DRY_RUN}")
        logger.info("═" * 60)

        # 1. Shared Hub
        self._hub = await IntelligenceHub.instance()
        self._hub._init_internals()
        await self._hub.connect()

        # 2. Signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._stop)

        # 3. Wire SignalBus → SentinelGateway bridge
        self._bus.subscribe_all(self._signal_to_gateway)
        logger.info("🔗 SignalBus → SentinelGateway bridge active")

        # 4. Launch Gateway + all sentinel tasks
        gateway_task = asyncio.create_task(self._gateway.run(), name="SentinelGateway")

        sentinels: List[BaseSentinelTask] = [
            cls(self._hub, self._gateway)
            for cls in self._sentinel_classes
        ]

        for sentinel in sentinels:
            t = asyncio.create_task(sentinel.run(), name=sentinel.name)
            self._tasks[sentinel.name] = t

        logger.info(f"✅ Launched {len(sentinels)} sentinel tasks + Gateway + Bus")

        # 4. Supervisor loop
        try:
            while self._running:
                if KILL_SWITCH.exists():
                    logger.warning("🛑 KILL SWITCH DETECTED. Shutting down Guardian.")
                    self._running = False
                    break

                await asyncio.sleep(self.TASK_RESTART_DELAY)
                self._cycle += 1

                # Check for crashed tasks and restart
                for sentinel in sentinels:
                    task = self._tasks.get(sentinel.name)
                    if task and task.done():
                        exc = task.exception() if not task.cancelled() else None
                        if exc:
                            logger.error(f"[Supervisor] Task {sentinel.name} crashed: {exc}. Restarting.")
                            from utils.helpers import audit_log
                            audit_log(f"Task {sentinel.name} crashed: {exc}", level="ERROR", component="GUARDIAN")
                        else:
                            logger.warning(f"[Supervisor] Task {sentinel.name} exited cleanly. Restarting.")
                        await asyncio.sleep(self.TASK_RESTART_DELAY)
                        sentinel._running = True
                        new_task = asyncio.create_task(sentinel.run(), name=sentinel.name)
                        self._tasks[sentinel.name] = new_task

                # Heartbeat
                if self._cycle % self.HEARTBEAT_INTERVAL == 0:
                    self._write_heartbeat(sentinels)

        except asyncio.CancelledError:
            pass
        finally:
            await self._shutdown(gateway_task, sentinels)

    async def _signal_to_gateway(self, signal: Signal) -> None:
        """Bridge: SignalBus → SentinelGateway → Telegram."""
        priority = 2 if signal.confidence > 0.8 else (3 if signal.confidence > 0.5 else 4)
        text = signal.payload.get("message", str(signal))
        await self._gateway.dispatch(AlertMessage(
            source=f"Bus/{signal.source}",
            priority=priority,
            text=text,
            dedup_key=f"bus_{signal.kind}_{signal.asset}",
        ))

    def _stop(self) -> None:
        logger.info("📡 Shutdown signal received.")
        self._running = False
        for t in self._tasks.values():
            t.cancel()
        self._gateway.stop()

    async def _shutdown(self, gateway_task: asyncio.Task,
                        sentinels: List[BaseSentinelTask]) -> None:
        logger.info("🛑 Shutting down Guardian Daemon...")
        
        # 1. Stop all sentinels first
        for s in sentinels:
            s.stop()
            
        # 2. Cancel all supervisor tasks
        for name, t in self._tasks.items():
            if not t.done():
                t.cancel()
        
        # 3. Stop gateway
        gateway_task.cancel()
        
        # 4. Wait for everything to wind down
        await asyncio.gather(*self._tasks.values(), gateway_task, return_exceptions=True)
        
        # 5. Close shared IntelligenceHub LAST
        if self._hub:
            await self._hub.close()
            
        logger.info("✅ Guardian Daemon stopped cleanly.")

    def _write_heartbeat(self, sentinels: List[BaseSentinelTask]) -> None:
        status = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "cycle": self._cycle,
            "hub_cache": self._hub.cache_stats if self._hub else "N/A",
            "tasks": {
                s.name: {
                    "cycles": s._cycles,
                    "errors": s._errors,
                    "running": self._tasks[s.name].done() is False,
                }
                for s in sentinels
            },
        }
        try:
            HBEAT_FILE.write_text(json.dumps(status, indent=2))
            logger.info(f"💓 Heartbeat #{self._cycle} | {self._hub.cache_stats if self._hub else ''}")
        except Exception as e:
            logger.warning(f"Heartbeat write failed: {e}")


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

async def main() -> None:
    daemon = GuardianDaemon()
    try:
        await daemon.run()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    except Exception as e:
        logger.critical(f"FATAL: {e}")
    finally:
        # Just in case run() didn't finish its finally block
        if daemon._hub:
            await daemon._hub.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    except Exception as e:
        logger.critical(f"Fatal error: {e}\n{traceback.format_exc()}")

# ============================================================
# BLOQUE NUEVO — Enriched alert dispatch (Unified Intelligence v1.0)
# ============================================================
# ============================================================
# BLOQUE NUEVO — Enriched alert dispatch (Unified Intelligence v1.0)
# ============================================================
def dispatch_enriched_alert(gateway_instance, curation_buffer,
                             signal_type: str, symbol: str, description: str,
                             core_hub=None):
    """
    Wrapper que crea un AlertSignal enriquecido y lo ingesta en el CurationBuffer.
    """
    async def _async_dispatch():
        try:
            from alerts.gateway import AlertSignal
            from core.hub_reader import get_live_metrics
            
            # Read real metrics from Hub
            m = await get_live_metrics(symbol=symbol)
            
            signal = AlertSignal(
                signal_type=signal_type,
                symbol=symbol,
                description=description,
                z_score_htf=m.z_htf,
                regime=m.regime,
                vpin=m.vpin,
                basis=m.basis,
                obi=m.obi,
            )
            curation_buffer.ingest(signal)
            
        except Exception as e:
            import logging
            logging.getLogger("ccxtv2.guardian").warning(
                f"[dispatch_enriched_alert] Error en despacho asíncrono: {e}"
            )

    # Dispatch as fire-and-forget task
    asyncio.create_task(_async_dispatch())
