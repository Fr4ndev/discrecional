# 🏛️ PHD INTELLIGENCE SYSTEM: ARCHITECTURAL SPECIFICATION

## 1. Overview
The CCXTV2 has been evolved into a Ph.D. level intelligence hub. It is no longer a collection of scripts, but a **Unified Reactive Brain** that processes market microstructure data in real-time to generate high-conviction institutional signals.

## 2. Core Components

### 🧠 Core Intelligence Hub (`core/Core_Intelligence_Hub.py`)
The "Ground Truth" engine. It maintains a single high-speed connection to the exchange (via CCXT) and calculates:
- **VPIN (Volume-synchronized Probability of Informed Trading)**: Toxicity index.
- **Institutional Basis**: Spot vs. Perp premium.
- **OBI (Order Book Imbalance)**: Real-time supply/demand pressure.
- **Elite Z-Scores**: Statistical deviations across multiple timeframes (HTF, Daily, Weekly).

### 🛰️ Hub Reader (`core/hub_reader.py`)
The standard interface for all system components. 
**RULE**: Never hardcode thresholds or calculate metrics locally. Always use `hub_reader.get_live_metrics()`.

### 🛡️ Guardian Daemon (`daemons/Guardian_Daemon.py`)
The supervisor of all sentinels. It orchestrates:
- **Ignition Bridge**: BTC to ETH rotation monitor.
- **Squeeze Monitor**: Short squeeze detection.
- **Spoof Detector**: Anti-spoofing logic via OBI snaps.
- **Senior Intelligence**: Fusing microstructure flips with price levels.
- **Whale Monitor**: Block-based institutional flow tracking.

### 📡 Signal Bus (`core/bus/__init__.py`)
An asynchronous pub/sub system that decouples sensors from actors.
- **Signals**: Typed events (`sfp_triggered`, `spoof_detected`).
- **Subscribers**: The Sentinel Gateway and Reactive Router listen to this bus.

### 🎭 Sentinel Gateway & Curation Buffer (`alerts/gateway.py`)
The system's "Mouthpiece".
- **Curation Buffer**: A 30-second window that aggregates multiple raw signals into a single **Unified Alpha Pulse**.
- **PhD Synthesis**: Applies Golden Rules (VPIN Gate) before broadcasting to Telegram.

### 🏎️ Reactive Router (`core/reactive_router.py`)
The automation engine. It maps signals to specific execution flows (`omega`, `turbo`, `intraday`, `scalp`) with:
- **VPIN Gates**: Only executes if toxicity is high enough.
- **Institutional Cooldowns**: Prevents API spamming and over-trading.

### 🤖 AI Analyst (`core/ai_analyst.py`)
A deterministic reasoning engine that provides on-demand audits using the `FLOWS_OPERATING_MANUAL.md` logic.

## 3. Specialized Extensions & Telemetry

### 🧪 Auto Senior Analyst (`auto_senior_analyst.py`)
The top-tier cognitive layer. It orchestrates all routines (Omega, Scalp, etc.), reads real-time outputs from the Action Server, and uses LLMs (DeepSeek) to generate human-readable institutional dossiers in `reports_history/`.

### 📊 ML Dashboard (`ml_dashboard.py`)
The system's "Visual Cortex". It monitors the `logs/execution_features.jsonl` telemetry stream to visualize:
- **Slippage Decay**: Impact of institutional orders on market liquidity.
- **Entropy Analysis**: Detection of market anomalies and high-toxicity events.
- **Strategy Alpha**: Performance comparison between TWAP and Market execution.

### 🏛️ Macro Intelligence & Levels (`get_htf_zscore` & `refresh_watchlist_levels`)
Integrated directly into the Action Server. It bridges macro statistical analysis (Z-Scores, Wyckoff Phases) and dynamic level generation with real-time microstructure.
- **Z-Score Logic**: Migrated from `run_htf_zscore.py`.
- **Level Logic**: Migrated from `scripts/update_levels.py`. Updates `data/watchlist_levels.json`.

### 🔄 Composite Workflow Routines (API-Native)
The system has been evolved to expose multi-step shell routines as single-call Action Server endpoints. This ensures atomicity and centralized orchestration.
- **Scalp Workflow (`run_scalp_workflow`)**: Unifies Toxicity (VPIN), Microstructure Audit, and D20 Walls. Replaces `scripts/routines/run_scalp_workflow.sh`.
- **Intraday Workflow (`run_intraday_workflow`)**: Unifies Basis Analysis, Tactical Reports, and D100 UDC Walls. Replaces `scripts/routines/run_intraday_workflow.sh`.
- **SFP Confluence (`detect_sfp_confluence`)**: Unifies Confluence Triggers and Ultra-Deep Confluence Walls. Replaces `scripts/routines/run_sfp_routine.sh`.
- **ELE Transition (`eth_ele_audit`)**: Specialized ETH Liquidity Engine audit for scalp-to-intraday transitions.

### 🧪 Visual & Cognitive Extensions
- **ML Dashboard (`ml_dashboard.py`)**: The system's "Visual Cortex". Streamlit-based visualization of `logs/execution_features.jsonl` telemetry.
- **Auto Senior Analyst (`auto_senior_analyst.py`)**: The top-tier cognitive layer. LLM-driven institutional dossier generation.

### 🛡️ Process Supervision & Daemons
- **Guardian Daemon (`daemons/Guardian_Daemon.py`)**: The high-level institutional supervisor.
- **Controller Daemon (`controller.py`)**: The local process manager and heartbeat supervisor for root-level operations.

## 6. Operations Manual

### Launch Sequence
1. Ensure `.env` is configured with valid API keys and Telegram credentials.
2. Run `./start_ccxtv2.sh`. This launches the Guardian, Controller, and Action Server in `tmux` sessions.

### Telegram Commands
- `/omega`: Full institutional audit (Ph.D. level).
- `/phd_turbo`: Microstructure audit.
- `/analysis <profile>`: Detailed AI analysis of a specific flow (e.g., `omega`, `sfp`, `scalp`).
- `/status`: System health and execution history.

## 4. Golden Rules (PhD Thresholds)
- **VPIN Gate**: `> 0.62` (Required for flow execution).
- **Basis Premium**: `< -0.05%` (Indicates institutional accumulation).
- **OBI Ignition**: `> 0.40` (Confirms supply/demand imbalance).

## 5. Maintenance & Evolution
- **Self-Improvement**: Post-mortem analysis is recorded in `.agents/workflows/self_improvement_routine.md`.
- **Strategic Updates**: Macro regime shifts are documented in `AI_OPS_STRATEGIC_INTELLIGENCE.md`.

---
*Verified & Validated: 30 Abril 2026*
