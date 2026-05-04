# Institutional Intelligence: Senior Desk Operating Manual

This manual distills the high-probability tactical flows and institutional-grade validation routines developed for the `ccxtv2` architecture.

## 🏛️ Tactical Flow: The Triple-Layer Audit

To validate any setup (Long or Short), follow this sequential routine:

1.  **Layer 1: Basis & Lead/Lag (The Foundation)**
    *   **Goal:** Determine if the move is driven by authentic "Physical" accumulation (Spot) or speculative "Leverage" (Perp).
    *   **Indicator:** `Basis %` (Spot Price - Perp Price / Perp Price * 100).
    *   **Rule:** If `Basis > 0.03%` and Spot is leading, the conviction is **High**. If Basis is negative (Backwardation), it's a **Trap**.
    *   **Script:** `python3 spot_perp_divergence.py`

2.  **Layer 2: OBI & Pulse (The Engine)**
    *   **Goal:** Detect immediate buy/sell pressure and whale aggression.
    *   **Indicator:** OBI (Order Book Imbalance) and Buy/Sell Ratio.
    *   **Rule:** OBI > 0.40 AND Ratio > 1.5 = **Ignition**.
    *   **Script:** `python3 volume_pulse.py` & `python3 eth_direct_check.py`

3.  **Layer 3: Spoof & Persistence (The Safety)**
    *   **Goal:** Filter out artificial walls (Spoofing).
    *   **Indicator:** OBI Snap Velocity.
    *   **Rule:** If OBI changes > 0.50 in under 30 seconds, it's a **Liquidity Pulling Alert**.
    *   **Script:** `python3 spoof_sentinel.py`

---

## 🛸 Advanced Setup: ETH Liquidity Engine (ELE)

This setup is designed to capture high-probability reversals at liquidity extremes and transition them into intraday trend-following positions.

| Component | Metric | Requirement |
| :--- | :--- | :--- |
| **Trigger** | SFP (Swing Failure) | Sweep of Daily H/L or H4 H/L. |
| **Scalp Confluence** | OBI | > 0.40 (Long) / < -0.40 (Short). |
| **Intraday Catalyst** | Basis Trend | Basis > 0.05% (Long) / Basis < 0.01% (Short). |

**Execution Protocol:**
1.  Open `eth_liquidity_engine.py` for automated monitoring.
2.  When an alert triggers, run `eth_ele_audit` via Action Server.
3.  If `Transition Potential = HIGH`, move SL to BE after Scalp TP1 and hold.

---

## 🛰️ Specialized Toolset (Sentinel Portfolio)

| Script | Purpose | When to Run |
| :--- | :--- | :--- |
| `eth_whale_sentinel.py` | Tracks trades > 50 ETH in real-time. | Always on (Daemon). |
| `ignition_monitor_bg.py` | Detects BTC/ETH coordinate breakouts. | During market trend search. |
| `find_order_book_walls.py` | Maps institutional SL/TP levels at Depth 2000. | Before entering any trade. |
| `senior_desk_audit.py` | Full Action Server REST validation. | Final Go/No-Go confirmation. |

---

## 🏎️ Master Prompt: "Senior Desk Initiation"

Copy and paste this prompt when starting a new session or seeking a high-conviction audit:

> "Actívate en modo **Senior Desk Analyst**. Realiza una auditoría de triple capa para [ASSET]:
> 1.  **Basis Check**: Ejecuta `spot_perp_divergence.py`. Si hay backwardation (< -0.03%), anula señales de Long.
> 2.  **Microstructure Audit**: Ejecuta `volume_pulse.py` y `eth_direct_check.py`. Busca Ratios > 1.5 y OBI > 0.40.
> 3.  **Anti-Spoofing Scan**: Revisa los logs de `spoof_sentinel.py`. Indica si ha habido 'OBI Snaps' (> 0.50) en el último minuto.
> 4.  **Statistical Horizon**: Cruza con el Z-Score de `get_zscore_vs_history`.
>
> Dame un dossier de inteligencia con veredicto final: REJECT (Trampa), NEUTRAL (Espera) o HIGH CONVICTION (Go)."

---

## ⚓ The "Golden Rules" of the Desk

*   **Rule of 30s:** If a signal is too good to be true (OBI 0.99), wait 30 seconds. If it stays, it's a rock; if it snaps, it's a bait.
*   **Decoupling is an Edge:** When BTC is weak but ETH Spot is leading, the probability of a "Short Squeeze" on ETH is at its peak.
*   **Volume Pulse > Price Action:** Never enter a breakout if the Volume Pulse Buy/Sell ratio is < 1.0. 
