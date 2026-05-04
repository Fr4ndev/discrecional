# 🏛️ CCXTV2 — Architecture Reference for AI Agents

This document provides a technical map of the `ccxtv2` ecosystem, enabling AI agents to navigate, analyze, and operate the platform effectively.

## 🏗️ 1. System Layers & Directory Mapping

| Layer | Directory | Responsibility | Key Symbols / Components |
| :--- | :--- | :--- | :--- |
| **Core** | `core/` | Brain & Data Engine | `IntelligenceHub`, `RedisCache`, `DataEngine` |
| **Supervision** | `daemons/` | 24/7 Monitoring | `GuardianDaemon`, `SFPAdvancedMonitor`, `IgnitionDaemon` |
| **Action Server** | `funding_action_server/` | On-Demand Analysis | `audit_actions.py`, `market_actions.py`, `absorption_detector.py` |
| **Strategies** | `strategies/` | Quantitative Logic | `zscore.py`, `spotdiff.py`, `eth_liquidity_engine.py` |
| **Alerting** | `alerts/` | Unified Notifications | `SentinelGateway`, `telegram.py` |
| **Scripts** | `scripts/` | Workflow Automation | `run_flows.sh`, `start_alpha_stack.sh` |
| **Interface** | Root & Others | UI & Control | `controller.py`, `ml_dashboard.py` |

---

## 🧠 2. God Nodes (Primary Entry Points)

- **`core/Core_Intelligence_Hub.py` → `IntelligenceHub`**: The singleton source of truth. Handles all exchange connections, real-time metric calculations (OBI, CVD, Basis, Toxicity), and caching.
- **`daemons/Guardian_Daemon.py` → `GuardianDaemon`**: The orchestrator. Monitors all background processes, manages heartbeats, and ensures system stability.
- **`alerts/gateway.py` → `SentinelGateway`**: The central hub for all alerts. Deduplicates and routes notifications to Telegram.

---

## 📡 3. Data & Communication Flow

1. **Ingestion**: `IntelligenceHub` fetches raw data from Exchanges (Spot/Futures).
2. **Analysis**: `Daemons` or `Action Server` call `IntelligenceHub` to compute microstructure metrics.
3. **Execution**: `Strategies` generate signals based on analyzed data.
4. **Notification**: `GuardianDaemon` or `Strategies` send events to `SentinelGateway`.
5. **Reporting**: Results are logged in `data/` and visualized via `ml_dashboard.py` or Telegram.

---

## 🛠️ 4. Operational Guidelines for Agents

### 🔍 Analysis Flow
When asked to analyze market conditions:
1. Check if the **Action Server** is running (`scripts/ops/status_check.sh`).
2. Utilize `scripts/ops/run_flows.sh` to trigger specific audits (e.g., `scalp`, `turbo`, `micro`).
3. Inspect JSON results in `data/snapshots/` (e.g., `data/snapshots/turbo_snapshot.json`).
4. Correlate with logs in `data/*.log` to understand daemon perspective.
5. Visual charts are stored in `data/charts/`.

### 🔧 Troubleshooting
- **Missing Data**: Ensure `IntelligenceHub` is healthy and Redis is running.
- **Alert Failures**: Check `SentinelGateway` logs and connectivity to Telegram API.
- **Daemon Crashes**: Consult `GuardianDaemon` logs for auto-restart events.

### 🚀 Command Standards
- **Running Routines**: Use scripts in `scripts/routines/`.
- **Testing**: Always use `scripts/run_all_tests.sh` before and after modifications.
- **Logs**: Real-time logs are located in `data/` for operational daemons and `logs/` for general system events.

---

## 📜 5. Standards & Conventions
- **Naming**: Snake_case for files, PascalCase for Classes.
- **Persistence**: Temporary state in `Redis`, persistent snapshots in `data/snapshots/`.
- **Integrity**: Never modify `core/` without running full unit tests.
