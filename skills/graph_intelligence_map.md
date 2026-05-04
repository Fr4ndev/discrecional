# 🕸️ CCXTV2 — Graph Intelligence & Relationship Map

This document analyzes the system's internal connectivity based on the latest Graphify analysis (April 2026). It identifies core hubs, hidden dependencies, and architectural improvement vectors.

## 🏆 1. The Trinity of God Nodes
The system revolves around three central pillars. High connectivity here means any change to these files has a massive blast radius.

| Node | Degree | Role | Risk Level |
| :--- | :--- | :--- | :--- |
| **`DataEngine`** | 115 | Backward-compatible shim. Bridges legacy code to the new Hub. | **CRITICAL** (Bottleneck) |
| **`IntelligenceHub`** | 94 | Process-wide singleton. Central data provider. | **HIGH** (Single Point of Truth) |
| **`TelegramService`** | 96 | Unified notification bridge. | **MEDIUM** (Operational Dependency) |

---

## 🏘️ 2. Community Analysis (Clusters of Logic)

### Community 1: Strategy & Quantitative Logic
- **Key Members**: `ZScoreEngine`, `SpotDiffEngine`, `OrderFlowEngine`, `HeatmapEngine`.
- **Status**: High cohesion. These modules are well-grouped but heavily dependent on `DataEngine`.
- **Improvement**: Migrate these to use `IntelligenceHub` directly to bypass the shim.

### Community 2: Core & Supervision
- **Key Members**: `IntelligenceHub`, `GuardianDaemon`, `ExecutionEngine`, `SFPAdvancedMonitor`.
- **Status**: This is the "Engine Room." It is stable but shows complex inferred relationships with the Action Server.

### Community 6 & 8: Specialized Audits
- **Key Members**: `AbsorptionDetector`, `audit_actions.py`, `ETHLiquidityEngine`.
- **Status**: These are "Action-Heavy" communities. They represent the high-level intelligence layer.

---

## 📈 3. Architectural Improvement Vectors

### 🚀 Vector A: "The Great Decoupling" (Bypass `DataEngine`)
- **Problem**: `DataEngine` has 115 edges, acting as a middleman for almost everything.
- **Action**: Sequentially update strategies in `strategies/` to import `IntelligenceHub` directly.
- **Goal**: Reduce `DataEngine` degree to < 20 (legacy only).

### 🛡️ Vector B: "Explicit over Inferred" (Confidence Boosting)
- **Problem**: 50% of edges are `INFERRED` (avg confidence 0.61). This means the AI/Graphify is "guessing" relationships based on usage rather than explicit imports/types.
- **Action**: 
  - Add explicit Type Hints (`from core.Core_Intelligence_Hub import IntelligenceHub`).
  - Use `__all__` in `__init__.py` files to define public interfaces.
- **Goal**: Increase `EXTRACTED` edges to > 80%.

### 📡 Vector C: "Unified Alerting"
- **Problem**: `TelegramService` is connected to 96 nodes directly.
- **Action**: Route all notifications through `SentinelGateway` (`alerts/gateway.py`).
- **Goal**: Make `SentinelGateway` the only node talking to `TelegramService`.

---

## 🔗 4. Hidden Relationships (The "Surprises")
- **Absorption vs Hub**: The `AbsorptionDetector` uses `IntelligenceHub` for multi-snapshot tracking. This link is currently inferred and should be made explicit to ensure reliability.
- **Guardian vs SFP**: `GuardianDaemon` supervises `SFPAdvancedMonitor` but also shares the `ExecutionEngine`. This creates a secondary control loop that must be monitored for race conditions.

---

## 🛠️ Operational Instructions for Agents
When modifying a God Node:
1. **Check blast radius**: Use `graphify explain [NodeName]` to see who depends on it.
2. **Prioritize Cohesion**: If adding a new feature, place it in the community that matches its logic (e.g., new indicators go to Community 10).
3. **Validate Bridges**: If a change affects `SentinelGateway` or `IntelligenceHub`, run the full integration suite.
