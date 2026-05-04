# 🏗️ CCXTV2 — Institutional Microstructure Architecture v2.0

## 1. Executive Summary
The `ccxtv2` system is a high-frequency market microstructure analysis platform designed for BTC and ETH. It consolidates multiple disparate engines into a unified **Intelligence Hub** that feeds real-time tactical data to a **Guardian Daemon** (Autonomous Monitor) and an **Action Server** (Interpreted Workflows).

## 2. Core Components

### 🧠 Intelligence Hub (`core/Core_Intelligence_Hub.py`)
The "Brain" of the system.
- **Singleton Pattern**: Ensures a single connection per process to exchanges (Binance, Bybit, OKX, Hyperliquid).
- **TTL Cache Layer**: Minimizes API calls and prevents 429 rate limiting.
- **PhD Metrics**: 
  - **VPIN / Toxicity**: Informed flow detection.
  - **OBI (Order Book Imbalance)**: Real-time pressure monitoring.
  - **CVD Velocity/Acceleration**: Aggressive flow confirmation.
  - **Basis Divergence**: Spot/Perp premium tracking.
  - **Wall Velocity**: Spoofing and ghost-wall detection.

### 🛡️ Guardian Daemon (`daemons/Guardian_Daemon.py`)
The "Protector" and supervisor.
- **7-Task Parallelism**: Monitors SFP, ELE, Funding, and Liquidity across assets.
- **Auto-Restart**: Built-in resilience for daemon crashes.
- **Sentinel Gateway**: Unified alert management with priority queuing and deduplication.

### 📡 Action Server (`funding_action_server/`)
The "Interpretable Interface" for agents and external tools.
- **RESTful Endpoints**: Exposes microstructure metrics via a standardized API.
- **Workflows**: `detect-confluence-trigger`, `microstructure-audit`, `get-tactical-report`.

### 🤖 Telegram Controller (`controller.py`)
The "User Interface".
- **Interactive Bot**: Allows users to query the system via `/heatmap`, `/orderflow`, `/zscore`, etc.
- **Real-time Alerts**: Forwards critical signals from the Guardian Gateway to the user.

## 3. Workflow Routines

| Routine | Purpose | Core Signal |
|:---|:---|:---|
| **FLOW-SCALP** | Capture 1-15m micro-trends | Toxicity > 0.6 + Absorption |
| **FLOW-INTRADAY**| Session Floor/Ceiling (1-4h) | Basis < -0.03% + Deep Walls |
| **SFP-CONFLUENCE**| Institutional Reversals | Daily H/L breach + Confluence > 70% |
| **ELE-TRANSITION**| ETH SFP to Trend capture | ETH-specific Liquidity Engine potential |

## 4. Maintenance & Health
- **Location**: `tests/`
- **Critical Tests**:
  - `test_intelligence_hub.py`: Core connectivity and snapshot sanity.
  - `test_funding_fees.py`: Anomaly detection and scraping health.
  - `test_absorption.py`: PhD metric calculation validation.

## 5. Deployment Guide
1. **Action Server**: `action-server start --port 8080 --dir funding_action_server`
2. **Controller**: `python3 controller.py`
3. **Guardian**: `python3 daemons/Guardian_Daemon.py`

---
*Senior Desk Documentation — April 2026*
