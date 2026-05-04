---
description: "FLOW-SWING: Cambio de Régimen — Posicionamiento HTF, OI Acumulación, y Divergencia de Spot Premium"
---

// turbo-all
# 🏗️ FLOW-SWING — Cambio de Régimen

**Horizon**: 1-5 días | **Frequency**: Once per session (after London open, before NY close)

## Selection Logic

| Endpoint | Por qué este y no otro | Señal clave |
|:---|:---|:---|
| `get-full-market-snapshot` | Capta Funding + OI + OBI en una sola call con historia. El OI acumulado durante varios días es la huella de la posición institucional HTF. | `oi_delta_pct` multi-exchange + `trigger_conservative` |
| `get-basis` | Backwardation *persistente* (varios días) = acumulación estructural. Es el diferenciador entre "compra intraday" y "compra de régimen". | `basis_pct` < -0.03% por > 2 sesiones |
| `get-tactical-report` (swing) | Contiene el Z-Score de 48h del funding + historia de OI. `max_abs_zscore > 2.0` = estadísticamente extremo. | `trigger_swing` = True (ΔOI > 10% AND Z-Score > 2.0) |

> **Por qué NO usamos** `microstructure-audit` ni `get-toxicity-index` aquí: el swing trade no se monta sobre flujo de minutos.
> **Por qué NO usamos** `get-ultra-deep-confluence` aquí: los muros del swing-level son de OI history, no de depth de libro puntual.

---

## Execution Script

```bash
# Variables
ASSETS="BTC,ETH"
BTC_SYM="BTC/USDT:USDT"
ETH_SYM="ETH/USDT:USDT"
BASE_URL="http://localhost:8080/api/actions/funding-action-server"

# ── PASO 1: Full Market Snapshot (OI + Funding + OBI acumulado) ─────────
curl -s -X POST "$BASE_URL/get-full-market-snapshot/run" \
  -H "Content-Type: application/json" \
  -d "{\"assets\": \"$ASSETS\", \"ob_depth\": 50}" \
  > swing_snapshot.json

# ── PASO 2: Basis multi-sesión (ancla de régimen) ──────────────────────
curl -s -X POST "$BASE_URL/get-basis/run" \
  -H "Content-Type: application/json" \
  -d '{"symbol_spot": "BTC/USDT", "symbol_perp": "BTC/USDT:USDT"}' \
  > swing_basis_btc.json &

curl -s -X POST "$BASE_URL/get-basis/run" \
  -H "Content-Type: application/json" \
  -d '{"symbol_spot": "ETH/USDT", "symbol_perp": "ETH/USDT:USDT"}' \
  > swing_basis_eth.json &

wait

# ── PASO 3: Tactical Report (swing mode — Z-Score 48h + OI history) ─────
curl -s -X POST "$BASE_URL/get-tactical-report/run" \
  -H "Content-Type: application/json" \
  -d "{\"assets\": \"$ASSETS\", \"strategy\": \"swing\"}" \
  > swing_tactical.json

echo "✅ FLOW-SWING complete."
echo "── Snapshot HTF:  swing_snapshot.json"
echo "── Basis Régimen: swing_basis_btc.json + swing_basis_eth.json"
echo "── Z-Score 48h:   swing_tactical.json"
```

---

## Alpha-Trigger (Regime Change Protocol)

```
ACUMULACIÓN ESTRUCTURAL (Long Swing):
[1] trigger_conservative == true     → OI > 10% AND Z-Score > 2.0 (snapshot)
[2] AND basis_pct < -0.03%           → Spot Premium confirmado (spot liderando perp)
[3] AND trigger_swing == true        → Confirmado por tactical-swing también
[4] AND interpretation == "Spot Premium (Accumulation)" en basis output
[5] CONFIRMAR: oi_delta_pct positivo en >= 3 de 4 exchanges

DISTRIBUCIÓN ESTRUCTURAL (Short Swing):
[1] trigger_conservative == true
[2] AND basis_pct > +0.05%           → Perp Premium (retailers late to the party)
[3] AND trigger_swing == true
[4] AND max_abs_zscore > 2.0         → Funding en zona estadísticamente extrema (shorts pago)
```

**Spot Premium Divergence (máxima señal):**
```
basis_pct < -0.05% (Backwardation fuerte) 
AND btc y eth simultáneamente en acumulación (OI expanding en ambos)
→ Régimen alcista multi-día. Hold swing con SL por debajo del low diario anterior.
```

---

## Decision Matrix

| `trigger_conservative` | `basis_pct` | `trigger_swing` | `max_abs_zscore` | Acción |
|:---|:---|:---|:---|:---|
| `True` | `< -0.03%` | `True` | `> 2.0` | ✅ **GO LONG SWING — full size** |
| `True` | `> +0.05%` | `True` | `> 2.0` | ✅ **GO SHORT SWING** |
| `True` | `< -0.03%` | `False` | `< 2.0` | 🟡 **WAIT — acumulación pero sin Z-Score extremo** |
| `False` | `< -0.03%` | `True` | `> 2.0` | 🟡 **PARTIAL — z-score extremo sin trigger OI consensus** |
| `False` | neutral | `False` | `< 1.5` | ❌ **NO TRADE — sin edge HTF** |

**Risk-Flip Rules (Swing — Críticos):**
- `trigger_conservative` pasa de `True` a `False` en la siguiente sesión → OI se liquidó → **CLOSE IMMEDIATELY**
- `basis_pct` cruza de negativo a positivo Y permanece positivo >6h → Spot ya no lidera → **REDUCE 50%**
- `max_abs_zscore` cae de > 2.0 a < 1.0 → Z-Score revertió a la media → **TOMAR TP PARCIAL**
- `interpretation` cambia a `"Perp Premium (Retail FOMO/Hedging)"` → **ABORT — el mercado se invirtió**

---

## Swing Position Management

```
ENTRY: En el primer cierre de vela H4 que confirme todos los triggers.
SL:    Por debajo del Low Diario anterior (o High Diario para shorts). No usar SL ajustado.
TP1:   +2.5% del precio de entrada (reducir 30% posición).
TP2:   Cuando basis_pct vuelva a NEUTRAL (0.00% ± 0.01%).
TP3:   Cuando trigger_conservative vuelva a False (OI empieza a distribuir).
```
