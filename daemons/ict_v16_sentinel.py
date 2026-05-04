#!/usr/bin/env python3
"""
daemons/ict_v16_sentinel.py — ICT Alpha v16 Sentinel
═══════════════════════════════════════════════════════════════════════════════
Implementation of the ICT Alpha Signal Bot v16.0 Alpha logic.
Monitors BTC/ETH for liquidity sweeps across 4 Tiers (1M, 1D, 4H, 1H).
"""

from __future__ import annotations

import asyncio
import calendar
import io
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd

from core.config import settings
from core.Core_Intelligence_Hub import IntelligenceHub
from alerts.gateway import SentinelGateway, AlertMessage
from daemons.base import BaseSentinelTask

logger = logging.getLogger("ICT_V16_Sentinel")

# ════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════════════════

ICT_CONFIG = {
    "DEV_LIMIT":         0.45,   # C1: Permite barridos hasta 45% del rango
    "TIMING_LIMIT":      0.85,   # C2: Permite sweeps hasta el 85% de la vela
    "MIN_RR":            1.4,    # RR Mínimo táctico
    "MIN_SCORE":         1.5,    # Score Mínimo para notificar
    "SL_ATR_MULT":       0.5,    # Buffer del Stop Loss sobre la mecha
    "IMPULSE_BODY_MIN":  0.45,   # Cuerpo mínimo de la vela previa
    "REQUIRE_MSS":       True,
    "FVG_LOOKBACK":      30,    # FVG general para intraday (15m)
    "FVG_RECENT_CANDLES": 3,   # FVG rápido sobre las últimas N velas del TF del sweep
    "COOLDOWN_H":        4,
    "FIB_TP1":           0.66,
    "FIB_TP2":           0.705,
    "FIB_TP3":           0.79,
}

TIERS = [
    {
        "tier": 1, "tf": "1M",  "label": "MONTHLY",
        "c2_seconds": int(30 * 86400 * 0.85),
        "base_score": 4.0,
        "emoji": "🚨", "priority": "TIER-1 ALARMA MÁXIMA",
    },
    {
        "tier": 2, "tf": "1d",  "label": "DAILY",
        "c2_seconds": int(24 * 3600 * 0.85),
        "base_score": 3.0,
        "emoji": "💎", "priority": "TIER-2 HIGH",
    },
    {
        "tier": 3, "tf": "4h",  "label": "4H",
        "c2_seconds": int(4 * 3600 * 0.85),
        "base_score": 2.0,
        "emoji": "⭐", "priority": "TIER-3 MEDIUM",
    },
    {
        "tier": 4, "tf": "1h",  "label": "1H",
        "c2_seconds": int(3600 * 0.85),
        "base_score": 1.0,
        "emoji": "📊", "priority": "TIER-4 STANDARD",
    },
]

ESTILO = mpf.make_mpf_style(
    base_mpf_style="nightclouds",
    rc={
        "figure.facecolor": "#0b0e11",
        "axes.facecolor": "#0b0e11",
        "axes.grid": False,
    },
)

_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001FFFF"  # emoticons & misc symbols
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\u2600-\u26FF"
    "\u2700-\u27BF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\u2000-\u206F"           # general punctuation block
    "\u2300-\u23FF"           # misc technical
    "\u25A0-\u25FF"           # geometric shapes
    "\u2B00-\u2BFF"           # misc symbols and arrows
    "]",
    flags=re.UNICODE,
)

def _strip_emoji(text: str) -> str:
    return _EMOJI_RE.sub("", text).strip()

class ICTAlphaV16Task(BaseSentinelTask):
    name = "ICT_V16"
    poll_interval = 900.0  # 15 minutes
    enabled_env_var = "DISABLE_ICT_V16"

    SYMBOLS = ["BTC/USDT:USDT", "ETH/USDT:USDT"]
    LTF_CHART = "15m"
    STATE_FILE = Path("/home/wek/Escritorio/ccxtv2/data/ict_v16_state.json")

    def __init__(self, hub: IntelligenceHub, gateway: SentinelGateway):
        super().__init__(hub, gateway)
        self._last_signal = {}
        self._load_state()

    def _load_state(self):
        if self.STATE_FILE.exists():
            try:
                with open(self.STATE_FILE) as f:
                    self._last_signal = json.load(f).get("LAST_SIGNAL", {})
            except Exception as e:
                self.log.error(f"load_state error: {e}")

    def _save_state(self):
        try:
            with open(self.STATE_FILE, "w") as f:
                json.dump({"LAST_SIGNAL": self._last_signal}, f)
        except Exception as e:
            self.log.error(f"save_state error: {e}")

    def _in_cooldown(self, key: str) -> tuple[bool, float]:
        if key not in self._last_signal:
            return False, 0.0
        elapsed_h = (
            datetime.now(timezone.utc)
            - datetime.fromisoformat(self._last_signal[key]).replace(tzinfo=timezone.utc)
        ).total_seconds() / 3600
        remaining_h = ICT_CONFIG["COOLDOWN_H"] - elapsed_h
        return elapsed_h < ICT_CONFIG["COOLDOWN_H"], max(remaining_h, 0.0)

    def _mark_sent(self, key: str):
        self._last_signal[key] = datetime.now(timezone.utc).isoformat()
        self._save_state()

    async def _cycle(self) -> None:
        session = self._get_session()
        for symbol in self.SYMBOLS:
            try:
                await self._analyze_symbol(symbol, session)
            except Exception as e:
                self.log.error(f"Error analyzing {symbol}: {e}")

    async def _analyze_symbol(self, symbol: str, session: dict) -> None:
        sym_short = symbol.split("/")[0]

        # 1. Multi-tier sweep scan
        sweep, df_sweep_tf = await self._scan_all_tiers(symbol)
        if sweep is None:
            return

        direction = sweep["sweep_type"]
        tier_num  = sweep["tier"]

        # 2. Cooldown
        ck = f"{sym_short}_{direction}_T{tier_num}"
        cd_active, cd_remaining_h = self._in_cooldown(ck)
        if cd_active:
            return

        # 3. Fetch 15m chart data
        df_15m = await self.hub.get_ohlcv(symbol, self.LTF_CHART, 150)
        if df_15m is None:
            return
        df_15m = self._add_indicators(df_15m)
        entry = float(df_15m["close"].iloc[-1])

        # 4. Indicators & Confluences
        order_flow = self._check_order_flow(df_15m, sweep)
        fvg = self._detect_fvg(df_15m, direction)
        fvg_recent = None
        if df_sweep_tf is not None and len(df_sweep_tf) >= 5:
            fvg_recent = self._detect_fvg_recent(df_sweep_tf, direction)

        mss_ok = self._check_mss(df_15m, sweep)
        atr = float(df_15m["atr"].iloc[-1])
        lvls = self._calc_sl_tps(sweep, atr)
        if lvls is None:
            return

        rr1 = self._calc_rr(entry, lvls["sl"], lvls["tp1"])
        if rr1 < ICT_CONFIG["MIN_RR"]:
            return

        lvls["entry"] = entry
        verdict = self._build_verdict(sweep, fvg, lvls, order_flow, mss_ok, session, entry, fvg_recent)

        if verdict["valid"]:
            await self._send_signal(entry, lvls, verdict, sweep, fvg, session, mss_ok, df_15m, symbol)
            self._mark_sent(ck)

    async def _scan_all_tiers(self, symbol: str) -> tuple[dict | None, pd.DataFrame | None]:
        fetch_limits = {"1M": 12, "1d": 60, "4h": 50, "1h": 50}
        for tier_info in TIERS:
            tf = tier_info["tf"]
            limit = fetch_limits.get(tf, 50)
            df_tf = await self.hub.get_ohlcv(symbol, tf, limit)

            if df_tf is None or len(df_tf) < 3:
                continue

            sweep = self._detect_sweep_for_tier(df_tf, tier_info)
            if sweep.get("sweep_type") is None:
                continue

            if not sweep["dev_ok"] or not sweep["timing_ok"]:
                continue

            return sweep, df_tf
        return None, None

    def _detect_sweep_for_tier(self, df_tf: pd.DataFrame, tier_info: dict) -> dict:
        NONE = {"sweep_type": None, "dev_ok": False, "timing_ok": False, "tier": tier_info["tier"]}
        if len(df_tf) < 3: return NONE

        prior = df_tf.iloc[-2]
        current = df_tf.iloc[-1]
        prior_l, prior_h = float(prior["low"]), float(prior["high"])
        curr_l, curr_h, curr_c, curr_o = float(current["low"]), float(current["high"]), float(current["close"]), float(current["open"])

        timing_ok, elapsed_s, limit_s = self._check_sweep_timing(df_tf, tier_info)
        impulse_body = abs(float(prior["close"]) - float(prior["open"])) / (prior_h - prior_l) if (prior_h - prior_l) > 0 else 0

        if curr_l < prior_l and curr_c > prior_l:
            dev_ok, D, H = self._check_deviation(current, prior, "BULLISH")
            lower_wick = min(curr_c, curr_o) - curr_l
            cr = curr_h - curr_l
            return {
                "sweep_type": "BULLISH", "swept_low_exact": curr_l, "swept_high_exact": curr_h,
                "prior_low": prior_l, "prior_high": prior_h, "prior_low_2": float(df_tf.iloc[-3]["low"]), "prior_high_2": float(df_tf.iloc[-3]["high"]),
                "wick_quality": round(lower_wick / cr, 3) if cr > 0 else 0,
                "dev_ok": dev_ok, "timing_ok": timing_ok, "D": D, "H": H, "dev_pct": round(D/H*100, 1) if H > 0 else 0,
                "elapsed_s": elapsed_s, "limit_s": limit_s, "tier": tier_info["tier"], "tier_label": tier_info["label"],
                "tier_emoji": tier_info["emoji"], "tier_priority": tier_info["priority"], "base_score": tier_info["base_score"], "impulse_body": impulse_body,
            }

        if curr_h > prior_h and curr_c < prior_h:
            dev_ok, D, H = self._check_deviation(current, prior, "BEARISH")
            upper_wick = curr_h - max(curr_c, curr_o)
            cr = curr_h - curr_l
            return {
                "sweep_type": "BEARISH", "swept_low_exact": curr_l, "swept_high_exact": curr_h,
                "prior_low": prior_l, "prior_high": prior_h, "prior_low_2": float(df_tf.iloc[-3]["low"]), "prior_high_2": float(df_tf.iloc[-3]["high"]),
                "wick_quality": round(upper_wick / cr, 3) if cr > 0 else 0,
                "dev_ok": dev_ok, "timing_ok": timing_ok, "D": D, "H": H, "dev_pct": round(D/H*100, 1) if H > 0 else 0,
                "elapsed_s": elapsed_s, "limit_s": limit_s, "tier": tier_info["tier"], "tier_label": tier_info["label"],
                "tier_emoji": tier_info["emoji"], "tier_priority": tier_info["priority"], "base_score": tier_info["base_score"], "impulse_body": impulse_body,
            }
        return NONE

    def _check_deviation(self, current: pd.Series, prior: pd.Series, direction: str) -> tuple[bool, float, float]:
        H = float(prior["high"]) - float(prior["low"])
        if H <= 0: return False, 0.0, 0.0
        D = (float(prior["low"]) - float(current["low"])) if direction == "BULLISH" else (float(current["high"]) - float(prior["high"]))
        ok = D > 0 and D <= H * ICT_CONFIG["DEV_LIMIT"]
        return ok, round(D, 6), round(H, 6)

    def _check_sweep_timing(self, df_tf: pd.DataFrame, tier_info: dict) -> tuple[bool, float, float]:
        if tier_info["tf"] == "1M":
            now = datetime.now(timezone.utc)
            _, days = calendar.monthrange(now.year, now.month)
            limit_s = (days * ICT_CONFIG["TIMING_LIMIT"]) * 86400
        else:
            limit_s = tier_info["c2_seconds"]
        candle_open = df_tf.index[-1].replace(tzinfo=timezone.utc) if df_tf.index[-1].tzinfo is None else df_tf.index[-1]
        elapsed = (datetime.now(timezone.utc) - candle_open).total_seconds()
        return elapsed <= limit_s, elapsed, limit_s

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        tr = pd.concat([df["high"] - df["low"], (df["high"] - df["close"].shift()).abs(), (df["low"] - df["close"].shift()).abs()], axis=1).max(axis=1)
        df["atr"] = tr.rolling(14).mean()
        return df

    def _get_session(self) -> dict:
        hour = datetime.now(timezone.utc).hour
        if 0 <= hour < 6: s, po3, em = "ASIA", "ACCUMULATION", "🟡"
        elif 7 <= hour < 10: s, po3, em = "LONDON KZ", "MANIPULATION", "🔴"
        elif 12 <= hour < 15: s, po3, em = "NY AM KZ", "DISTRIBUTION", "🟢"
        elif 15 <= hour < 17: s, po3, em = "NY PM", "DISTRIBUTION_L", "🔵"
        else: s, po3, em = "OFF-HOURS", "CONSOLIDATION", "⚪"
        return {"session": s, "po3": po3, "emoji": em, "active": po3 in ("MANIPULATION", "DISTRIBUTION"), "time_str": datetime.now(timezone.utc).strftime("%H:%M UTC")}

    def _detect_fvg(self, df: pd.DataFrame, direction: str) -> dict | None:
        fvgs = []
        lookback = min(ICT_CONFIG["FVG_LOOKBACK"], len(df) - 3)
        last_px = float(df["close"].iloc[-1])
        for offset in range(lookback):
            i = len(df) - 1 - offset
            if i < 2: break
            c0h, c2l = float(df["high"].iloc[i-2]), float(df["low"].iloc[i])
            c0l, c2h = float(df["low"].iloc[i-2]), float(df["high"].iloc[i])
            if direction == "BULLISH" and c2l > c0h:
                if not any(float(df["low"].iloc[j]) <= c2l for j in range(i+1, len(df))):
                    fvgs.append({"type": "bullish", "top": c2l, "bottom": c0h, "mid": (c2l+c0h)/2})
            elif direction == "BEARISH" and c2h < c0l:
                if not any(float(df["high"].iloc[j]) >= c2h for j in range(i+1, len(df))):
                    fvgs.append({"type": "bearish", "top": c0l, "bottom": c2h, "mid": (c0l+c2h)/2})
        if not fvgs: return None
        fvgs.sort(key=lambda g: abs(g["mid"] - last_px))
        return fvgs[0]

    def _detect_fvg_recent(self, df: pd.DataFrame, direction: str) -> dict | None:
        n = ICT_CONFIG["FVG_RECENT_CANDLES"]
        if len(df) < n + 2: return None
        for offset in range(n):
            i = len(df) - 1 - offset
            if i < 2: break
            c0h, c2l = float(df["high"].iloc[i-2]), float(df["low"].iloc[i])
            c0l, c2h = float(df["low"].iloc[i-2]), float(df["high"].iloc[i])
            if direction == "BULLISH" and c2l > c0h:
                if not any(float(df["low"].iloc[j]) <= c2l for j in range(i+1, len(df))):
                    return {"type": "bullish", "top": c2l, "bottom": c0h, "mid": (c2l+c0h)/2, "source": "recent"}
            elif direction == "BEARISH" and c2h < c0l:
                if not any(float(df["high"].iloc[j]) >= c2h for j in range(i+1, len(df))):
                    return {"type": "bearish", "top": c0l, "bottom": c2h, "mid": (c0l+c2h)/2, "source": "recent"}
        return None

    def _check_mss(self, df_ltf: pd.DataFrame, sweep: dict) -> bool:
        if not ICT_CONFIG["REQUIRE_MSS"]: return True
        last = float(df_ltf["close"].iloc[-1])
        return last > sweep.get("prior_high_2", 1e18) if sweep["sweep_type"] == "BULLISH" else last < sweep.get("prior_low_2", -1e18)

    def _check_order_flow(self, df_ltf: pd.DataFrame, sweep: dict) -> bool:
        last = float(df_ltf["close"].iloc[-1])
        return last > sweep.get("prior_low", 1e18) if sweep["sweep_type"] == "BULLISH" else last < sweep.get("prior_high", -1e18)

    def _calc_sl_tps(self, sweep: dict, atr: float) -> dict | None:
        if pd.isna(atr) or atr <= 0: return None
        buf, H = atr * ICT_CONFIG["SL_ATR_MULT"], sweep["H"]
        if H <= 0: return None
        if sweep["sweep_type"] == "BULLISH":
            sw = sweep["swept_low_exact"]
            return {"direction": "BULLISH", "swept": sw, "sl": sw - buf, "tp1": sw + H * ICT_CONFIG["FIB_TP1"], "tp2": sw + H * ICT_CONFIG["FIB_TP2"], "tp3": sw + H * ICT_CONFIG["FIB_TP3"]}
        sw = sweep["swept_high_exact"]
        return {"direction": "BEARISH", "swept": sw, "sl": sw + buf, "tp1": sw - H * ICT_CONFIG["FIB_TP1"], "tp2": sw - H * ICT_CONFIG["FIB_TP2"], "tp3": sw - H * ICT_CONFIG["FIB_TP3"]}

    def _calc_rr(self, entry: float, sl: float, tp: float) -> float:
        risk = abs(entry - sl)
        return round(abs(tp - entry) / risk, 2) if risk > 0 else 0.0

    def _build_verdict(self, sweep: dict, fvg: dict | None, lvls: dict, of: bool, mss: bool, session: dict, entry: float, fvg_recent: dict | None) -> dict:
        score, conf = 0.0, []
        direction = sweep["sweep_type"]
        base = sweep.get("base_score", 1.0)
        score += base
        conf.append(f"{sweep['tier_emoji']} Sweep {sweep['tier_label']} {'SSL' if direction=='BULLISH' else 'BSL'} | D={sweep['dev_pct']:.1f}% | Base {base:.1f}")
        if sweep.get("wick_quality", 0) > 0.60:
            score += 0.5; conf.append("Rechazo fuerte ✅ | +0.5")
        if sweep.get("impulse_body", 0) > ICT_CONFIG["IMPULSE_BODY_MIN"]:
            score += 0.5; conf.append(f"Impulso Previo ({sweep['impulse_body']:.0%}) ✅ | +0.5")
        if fvg_recent:
            score += 1.0; conf.append(f"FVG Escape {fvg_recent['type'].upper()} ✅ | +1.0")
        if fvg:
            score += 1.0; conf.append(f"FVG Intraday ✅ | +1.0")
            if fvg["bottom"] <= entry <= fvg["top"]: score += 0.5; conf.append("Precio EN FVG ✅ | +0.5")
        if of: score += 1.0; conf.append("Order Flow Reversal ✅ | +1.0")
        if mss: score += 1.0; conf.append("MSS confirmado ✅ | +1.0")
        rr1 = self._calc_rr(entry, lvls["sl"], lvls["tp1"])
        if rr1 >= ICT_CONFIG["MIN_RR"]: score += 1.0; conf.append(f"RR={rr1:.1f} ✅ | +1.0")
        if session["active"]: score += 0.5; conf.append(f"Killzone {session['session']} ✅ | +0.5")

        quality = "🚨 MAX ALARM" if score >= 8 else "🏆 MAX" if score >= 7 else "💎 HIGH" if score >= 5 else "⭐ MED" if score >= 3 else "⚠️ LOW"
        return {"direction": direction, "score": round(score, 1), "max_score": 10.0, "quality": quality, "confluence": conf, "valid": score >= ICT_CONFIG["MIN_SCORE"]}

    async def _send_signal(self, entry, lvls, verdict, sweep, fvg, session, mss_ok, df_15m, symbol) -> None:
        chart_bytes = self._create_chart(df_15m, entry, lvls, session, verdict, sweep, symbol)
        caption, extra = self._build_message(entry, lvls, verdict, sweep, fvg, session, mss_ok, symbol)
        
        await self.gateway.dispatch(AlertMessage(
            source=f"ICT_V16_{sweep['tier_label']}",
            priority=1 if sweep["tier"] == 1 else 2,
            text=caption,
            photo=chart_bytes,
            dedup_key=f"ict_v16_{symbol}_{sweep['tier']}_{verdict['direction']}"
        ))
        if extra:
            await self.gateway.dispatch(AlertMessage(
                source=f"ICT_V16_Details",
                priority=3,
                text=extra,
                dedup_key=f"ict_v16_details_{symbol}_{sweep['tier']}"
            ))

    def _create_chart(self, df_15m: pd.DataFrame, entry: float, lvls: dict, session: dict, verdict: dict, sweep: dict, symbol: str) -> bytes:
        buf = io.BytesIO()
        h_vals, h_cols, h_stls, h_wids = [], [], [], []
        def _l(v, c, s="-", w=1.0):
            if v and not pd.isna(v): h_vals.append(v); h_cols.append(c); h_stls.append(s); h_wids.append(w)
        _l(entry, "#FFFFFF", "--", 1.2)
        _l(lvls.get("swept"), "#888888", ":", 1.0)
        _l(lvls.get("sl"), "#FF4444", "-", 2.0)
        _l(lvls.get("tp1"), "#FFD700", "-", 1.3)
        _l(lvls.get("tp2"), "#FFA500", "-", 1.3)
        _l(lvls.get("tp3"), "#FF6347", "-", 1.3)

        title = _strip_emoji(f"{symbol} (15m) | ICT v16 | Tier {sweep['tier']} {sweep['tier_label']} | Score {verdict['score']}")
        fig, axes = mpf.plot(df_15m, type="candle", style=ESTILO, title=title, hlines=dict(hlines=h_vals, colors=h_cols, linestyle=h_stls, linewidths=h_wids), figsize=(14, 8), returnfig=True, tight_layout=True)
        ax = axes[0]
        n = len(df_15m)
        sw, H = lvls.get("swept"), sweep.get("H", 0)
        if sw and H > 0:
            if verdict["direction"] == "BULLISH": ax.axhspan(sw - H * ICT_CONFIG["DEV_LIMIT"], sw, color="#00C853", alpha=0.12)
            else: ax.axhspan(sw, sw + H * ICT_CONFIG["DEV_LIMIT"], color="#FF1744", alpha=0.12)

        fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="#0b0e11")
        plt.close(fig)
        return buf.getvalue()

    def _build_message(self, entry, lvls, verdict, sweep, fvg, session, mss_ok, symbol) -> tuple[str, str | None]:
        sym = symbol.split("/")[0]
        dir_icon = "🟢 LONG" if verdict["direction"] == "BULLISH" else "🔴 SHORT"
        sep = "⎯" * 15
        header = f"🚨 *TIER 1 — MONTHLY*\n" if sweep["tier"] == 1 else f"{sweep['tier_emoji']} *{sweep['prior_priority'] if 'prior_priority' in sweep else sweep['tier_label']}*\n"
        
        caption = (
            f"{header}"
            f"*{sym}* | {dir_icon} | *{verdict['quality']}*\n"
            f"Score: `{verdict['score']}/10`\n"
            f"{sep}\n"
            f"💰 *ENTRY:* `{entry:.2f}`\n"
            f"🛡️ *SL:* `{lvls['sl']:.2f}`\n"
            f"🎯 *TP1:* `{lvls['tp1']:.2f}`\n"
            f"{sep}\n"
            f"⚡ {session['emoji']} {session['session']} | {session['po3']}\n"
        )
        extra = "📊 *Confluence Details:*\n" + "\n".join(f"• {c}" for c in verdict["confluence"])
        return caption, extra

    def _format_time(self, seconds: float) -> str:
        if seconds >= 86400: return f"{seconds/86400:.1f}d"
        if seconds >= 3600: return f"{seconds/3600:.1f}h"
        return f"{seconds/60:.0f}m"
