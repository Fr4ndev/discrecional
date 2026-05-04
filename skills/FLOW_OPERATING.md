# 🚀 FLOW OPERATING MANUAL — High-Conviction Institutional Intelligence

Este manual documenta el protocolo operativo para la ejecución de flujos de microestructura institucional. El objetivo es identificar **Informed Alpha**, **Liquidity Imbalances** y **Institutional Absorption** en tiempo real para BTC y ETH.

---

## 🔬 Core Workflows

### 1. FLOW-SCALP — Micro-Tendencia Explosiva
**Horizonte**: 1-15 min | **Frecuencia**: Cada 3-5 min.
- **Toxicity Index**: Detecta flujo informado (VPIN > 0.7).
- **Microstructure Audit**: Valida combustible OBI D20 + CVD.
- **OB Walls D20**: Localiza muros inmediatos ("landmines").

### 2. FLOW-INTRADAY — Captura de Sesión
**Horizonte**: 1-4 horas | **Frecuencia**: Apertura de sesión (London/NY).
- **Basis Protocol**: Define el Floor/Ceiling de la sesión (Spot vs Perp).
- **Ultra-Deep Confluence**: Muros institucionales D100 multi-exchange.
- **Tactical Report**: Dual-mode OBI y acumulación de OI.

### 3. ALPHA IGNITION — Detección de Impulso
- Identifica si un movimiento es **Institutional Ignition** o **Retail FOMO/Exhaustion**.

### 4. ELE TRANSITION (ETH Only) — Liquidity Engine
- Captura de SFPs en ETH y transición a posiciones intradía de alta probabilidad.

---

## 🧠 Master Decision Matrix (Quick Glance)

| Escenario | Señal Primaria | Confirmación | Acción |
|:---|:---|:---|:---|
| **High Conviction Long** | Toxicity > 0.7 + OBI > 0.4 | CVD Positive + Basis < 0 | ✅ **GO LONG** |
| **High Conviction Short** | Toxicity > 0.7 + OBI < -0.4 | CVD Negative + Basis > 0 | ✅ **GO SHORT** |
| **Absorption Trap** | Price Up + CVD Positive | OBI < -0.3 (Muros absorbiendo) | ⚠️ **NO TRADE** |
| **Retail FOMO** | Price Up + OBI > 0.5 | Basis Positive (Perp Premium) | 🔴 **SCALP ONLY** |

---

## 🛠️ Operational Commands

```bash
# Iniciar Servidor (Port 8080)
action-server start --port 8080 --dir .

# Ejecutar Auditoría Completa
/flow-scalp
/flow-intraday
/alpha-ignition
/sfp-confluence
```

---

> [!IMPORTANT]
> Siempre verificar el **HTF ELITE Z-SCORE** antes de escalar posiciones. Si el Score 1M < 40, los largos son de alta volatilidad y baja convicción.
