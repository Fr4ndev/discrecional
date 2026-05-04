---
description: "FLOW-INTRADAY: Captura de Sesión — Clusters Institucionales y Basis como Ancla de Floor/Ceiling"
---

// turbo-all
# 📊 FLOW-INTRADAY — Captura de Sesión

**Horizon**: 1-4 horas | **Frequency**: At session open (London/NY) and after major liquidity events

## Selection Logic

| Endpoint | Por qué este y no otro | Señal clave |
|:---|:---|:---|
| `get-tactical-report` (scalp + intraday) | Bifurca el análisis en OBI real-time (scalp) y acumulación de OI. El reporte scalp da el OBI máximo del libro D20; el intraday da el delta de OI para calcular el rango de sesión. | `max_obi` del frame scalp, `max_oi_delta_pct` del frame intraday |
| `get-ultra-deep-confluence` (depth 100) | 100 niveles detectan muros institucionales *reales* que no se verán en depth 20. Consensus multi-exchange (>75% = muro genuino). | `confidence_score >= 50` + `confluence_pct` |
| `get-basis` | El Basis es el ancla de la sesión: backwardation = Floor de spot, contango extremo = Ceiling. No incluimos OI ni funding separados porque `get-ultra-deep-confluence` ya los consolida. | `basis_pct` → Floor/Ceiling definition |

> **Por qué NO usamos** `get-toxicity-index` aquí: la toxicidad es ruido en horizontal de 1-4h. Lo que importa es la *presión acumuladora* (OI + Confluence), no si el trade individual es informado.

---

## Execution Script

```bash
# Variables
ASSETS="BTC,ETH"
BTC_SYM="BTC/USDT:USDT"
ETH_SYM="ETH/USDT:USDT"
BASE_URL="http://localhost:8080/api/actions/funding-action-server"

# ── PASO 1: Basis — Floor/Ceiling de la sesión ─────────────────────────
curl -s -X POST "$BASE_URL/get-basis/run" \
  -H "Content-Type: application/json" \
  -d '{"symbol_spot": "BTC/USDT", "symbol_perp": "BTC/USDT:USDT"}' \
  > intraday_basis_btc.json &

curl -s -X POST "$BASE_URL/get-basis/run" \
  -H "Content-Type: application/json" \
  -d '{"symbol_spot": "ETH/USDT", "symbol_perp": "ETH/USDT:USDT"}' \
  > intraday_basis_eth.json &

wait

# ── PASO 2: Tactical Report (dual mode) ────────────────────────────────
curl -s -X POST "$BASE_URL/get-tactical-report/run" \
  -H "Content-Type: application/json" \
  -d "{\"assets\": \"$ASSETS\", \"strategy\": \"scalp\"}" \
  > intraday_tactical_scalp.json &

curl -s -X POST "$BASE_URL/get-tactical-report/run" \
  -H "Content-Type: application/json" \
  -d "{\"assets\": \"$ASSETS\", \"strategy\": \"swing\"}" \
  > intraday_tactical_swing.json &

wait

# ── PASO 3: Ultra-Deep Confluence D100 (mapa institucional) ────────────
curl -s -X POST "$BASE_URL/get-ultra-deep-confluence/run" \
  -H "Content-Type: application/json" \
  -d "{\"assets\": \"$ASSETS\", \"depth\": 100}" \
  > intraday_udc.json

echo "✅ FLOW-INTRADAY complete."
echo "── Floor/Ceiling: intraday_basis_*.json"
echo "── Confluencia:   intraday_udc.json"
echo "── Táctico:       intraday_tactical_scalp.json + intraday_tactical_swing.json"
```

---

## Alpha-Trigger (Session Floor/Ceiling Protocol)

```
SESSION FLOOR (Long Setup):
[1] basis_pct < -0.03%          → Spot liderando, Backwardation = Floor institucional
[2] AND confidence_score >= 50  → Muro de compra multi-exchange confirmado
[3] AND direction == "LONG_BIAS" (de get-ultra-deep-confluence)
[4] AND trigger_scalp == true   → OBI D20 max > 0.45 en reporte táctico

SESSION CEILING (Short Setup):
[1] basis_pct > +0.05%          → Perp liderando, Contango extremo = Ceiling retail FOMO
[2] AND confidence_score >= 50  → Muro de venta multi-exchange confirmado
[3] AND direction == "SHORT_BIAS"
[4] AND trigger_scalp == true
```

**Intraday Target Logic:**
```
FLOOR de sesión = precio actual - distancia al top_support_bid más cercano (de UDC)
CEILING de sesión = precio actual + distancia al top_resistance_ask más cercano (de UDC)
Si (CEILING - FLOOR) / precio > 0.8% → Sesión con range suficiente para intraday
```

---

## Decision Matrix

| `basis_pct` | `confidence_score` | `direction` (UDC) | `max_obi` (táctico) | Acción |
|:---|:---|:---|:---|:---|
| `< -0.03%` | `≥ 50` | `LONG_BIAS` | `> 0.35` | ✅ **GO LONG — intraday** |
| `> +0.05%` | `≥ 50` | `SHORT_BIAS` | `< -0.35` | ✅ **GO SHORT — intraday** |
| `< -0.03%` | `< 50` | `LONG_BIAS` | `> 0.20` | 🟡 **PARTIAL — scalp only** |
| `-0.03% < x < +0.05%` | any | `NEUTRAL` | any | ⏸️  **WAIT — no directional anchor** |
| any | any | any | OBI flips sign | 🔴 **RISK-FLIP: ABORT** |

**Risk-Flip Rules:**
- `confidence_score` cae de >= 50 a < 30 → Muros fueron absorbidos, nivel roto → **ABORT LONG**
- `basis_pct` cruza de negativo a positivo durante la posición → Spot deja de liderar → **TIGHTEN SL**
- `trigger_swing` se activa (`max_oi_delta_pct > 10%`) → Hay acumulación HTF, **no cerrar early**
