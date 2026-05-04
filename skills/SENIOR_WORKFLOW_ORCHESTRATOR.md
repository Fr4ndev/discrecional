# 🧠 Skill: Senior Workflow Orchestrator (PhD Integration)

Esta skill consolida el mapeo, ejecución y perfilado de todos los flujos institucionales del proyecto CCXTV2. Proporciona una visión holística del ecosistema de agentes y rutinas.

---

## 🗺️ 1. Mapeo del Ecosistema (.agents/workflows)

| Workflow | Propósito Institucional | Frecuencia | Key Metric |
| :--- | :--- | :--- | :--- |
| **Flow-Scalp** | Captura de micro-tendencia | 3-5 min | `toxicity_index` (VPIN) |
| **Flow-Intraday** | Localización de Floor/Ceiling | Aperturas | `basis_pct` + `udc_confidence` |
| **Flow-Swing** | Cambio de régimen HTF | Diario | `trigger_conservative` (OI Accum) |
| **Alpha Ignition** | Detección de "Smart Money" | Real-time | `momentum_cluster` |
| **SFP Confluence** | Reversiones en niveles clave | Event-driven | `confluence_pct` |
| **ETH ELE** | Transición Scalp -> Intraday | Especializado | `transition_potential` |

---

## 🚀 2. Ejecución Maestra (Ignition)

Se ha creado el script `ignite_all_flows.sh` que dispara todos los flujos concurrentemente, utilizando tokens de autorización válidos y guardando resultados en `data/ignition_results_YYYYMMDD_HHMMSS/`.

### Uso:
```bash
bash ignite_all_flows.sh
```

---

## 📊 3. Perfilado de Resultados (Veredicto Técnico)

El perfilado se basa en la confluencia multi-horizonte:

- **Efecto Ancla (Basis):** Si el Basis es negativo (Spot Premium), los flujos de Scalp tienen un sesgo alcista de alta probabilidad.
- **Efecto Filtro (Toxicity):** Ningún flujo de Scalp es ejecutable si `toxicity_index < 0.62`, independientemente del OBI.
- **Efecto Confluencia (UDC):** Los niveles intraday solo se consideran "paredes reales" con un `confidence_score > 50`.

---

## 🛠️ 4. Vectores de Mejora & Add-ons (Futuro)

### A. Real-time Risk-Flip Engine (Add-on)
- **Concepto:** Un daemon que monitorea el output de `ignite_all_flows.sh` y detecta cambios de signo bruscos en el OBI o caídas de toxicidad en < 30s.
- **Mejora:** Reducción de drawdown en trades de scalp.

### B. Multi-Asset Rotation Scoring (Vector)
- **Concepto:** Integrar el scoring de SOL e HYPE (vistos en `alpha_snapshot`) con el liderazgo de BTC.
- **Mejora:** Detectar cuándo el Alpha se está moviendo de BTC a Alts (Rotation Phase).

### C. Z-Score Mean Reversion Watcher (Add-on)
- **Concepto:** Alertar cuando el `max_abs_zscore` en `swing_tactical.json` llega a > 3.0.
- **Mejora:** Captura de techos/suelos macro estadísticos.

---
*Documentación generada integralmente para el 0.1% de Senior Quants.*
