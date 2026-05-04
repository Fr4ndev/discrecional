# 🏗️ Technical Master Context: Institutional Surveillance Engine (ccxtv2)

This document provides the high-level technical architecture and logic of the current surveillance system to enable advanced AI iterations to optimize and evolve the platform.

## 1. Core Philosophy: The Microstructure Edge
The system moves beyond simple indicator-based trading. It focuses on **Market Microstructure (MMS)**:
- **OBI (Order Book Imbalance)**: Detecting one-sided liquidity that signals pending institutional moves or spoofing.
- **CVD (Cumulative Volume Delta) Ratio**: Measuring the aggression of buyers vs sellers in the last 200-500 trades.
- **Basis Divergence**: Monitoring the spread between Spot and Perpetual markets to detect hedging or speculative pressure.
- **SFP (Swing Failure Pattern)**: Using HTF levels combined with OBI/CVD to identify liquidity grabs (rejections).

---

## 2. Daemon Architecture
Currently, there are three specialized asynchronous daemons:

| Component | Logic | State Management |
| :--- | :--- | :--- |
| [opportunity_sentinel.py](file:///home/wek/Escritorio/ccxtv2/daemons/opportunity_sentinel.py) | **Flip Recognition**. Identifies rapid changes in OBI/CVD regimes. | Uses [AssetState](file:///home/wek/Escritorio/ccxtv2/daemons/opportunity_sentinel.py#114-126) to track `last_obi` and `last_cvd` for flip detection. |
| [squeeze_watcher.py](file:///home/wek/Escritorio/ccxtv2/daemons/squeeze_watcher.py) | **Linear Scoring**. Combines Funding, OBI, and CVD into a 0-3 score. | High-conviction threshold (3/3) triggers definitive tactical dossiers. |
| [level_break_alert.py](file:///home/wek/Escritorio/ccxtv2/daemons/level_break_alert.py) | **Geometric Trigger**. Monitors proximity to D1/4H levels. | Classifies price action as `ABOVE`, `BELOW`, or `AT` level, detecting transitions. |

---

## 3. The Signal Engine Logic (Advanced Integration)

### OBI Flip Logic
A "Flip" is defined when OBI crosses a zero-threshold after being pinned at an extreme:
- **Bullish Flip**: `prev_obi < -0.30` AND `current_obi > -0.05`.
- This signals that the "Sell Wall" has either been pulled (Spoofing) or successfully eaten (Absorption).

### Squeeze Scoring
- `Score += 1` if `Funding Rate < -0.005%` (Shorts pay Longs).
- `Score += 1` if `OBI > +0.20`.
- `Score += 1` if `CVD Ratio > 1.4`.
- **Handoff Objective**: Transform this linear score into a **Bayesian Probability Model** using historical drift.

---

## 4. Current Workflows & Handlers
- **Telegram Service**: Centralized in [alerts/telegram.py](file:///home/wek/Escritorio/ccxtv2/alerts/telegram.py). Uses `requests.post` inside daemons for reliability.
- **Data Engine**: Unified fetching in [core/data_engine.py](file:///home/wek/Escritorio/ccxtv2/core/data_engine.py) (ccxt-based).
- **Settings**: Centralized YAML/ENV in [core/config.py](file:///home/wek/Escritorio/ccxtv2/core/config.py).

---

## 5. Optimization Roadmap (AI-to-AI Handoff)

> [!IMPORTANT]
> **Priority 1: Latency Reduction**
> Move from Polling/REST to **Websocket Streams** for OBI and Trades. The current 10s-20s interval is fine for 4H/Intraday but needs <1s for true Scalp execution.
>
> **Priority 2: Auto-Level Generation**
> Integrate a script that updates [data/watchlist_levels.json](file:///home/wek/Escritorio/ccxtv2/data/watchlist_levels.json) using D1 fractal highs/lows and Volume Profile (POC/VAH/VAL) every hour.
>
> **Priority 3: Execution Loop**
> Create an `execution_daemon.py` that, upon receiving a "Score=3/3" signal from the watchers, interacts with the `Action Server` to place bracket orders (Limit Entry, Hard SL, TP ladder).

---

## 6. How to Extend This System
1. **Adding Metrics**: Integrate `absorption_detector.py` metrics (Velocity, Tick Divergence) into the `opportunity_sentinel`.
2. **Adding Assets**: Expand the `ASSETS` list in config to include SOL, TAO, and other volatile perpetuals.
3. **Machine Learning Layer**: Train a classifier on the captured logs (saved in `data/*.log`) to identify which "OBI Flips" lead to >1.5% moves.

---
*Signed: Antigravity Core Intelligence*
