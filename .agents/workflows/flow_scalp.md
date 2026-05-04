---
description: "FLOW-SCALP: Explosión de Micro-Tendencia — Toxicidad, Absorción y Desequilibrio del Book"
---

// turbo-all
# 🔬 FLOW-SCALP — Explosión de Micro-Tendencia

**Horizon**: 1-15 minutos | **Frequency**: Every 3-5 minutes during active sessions

## Selection Logic

| Endpoint | Por qué este y no otro | Señal clave |
|:---|:---|:---|
| `get-toxicity-index` | Es el único endpoint que detecta flujo *informado* (VPIN). Retailers no dejan huella de iceberg ni Kyle's λ alto. | `toxicity_index > 0.7` = traders con información dominan |
| `microstructure-audit` | Combustible la OBI D20 + CVD de 100 trades en una sola call. Latencia mínima. | `obi_20 > |0.40|` + `cvd_100_trades_usd` alineado |
| `get-ob-walls` (depth 20) | Profundidad 20 = muros *scalp-relevantes* (los que se barrán en <15 min). Depth 100 diluye la señal. | Top-3 support/resistance inmediatos |

> **Por qué NO usamos** `get-full-market-snapshot` aquí: incluye OI e historia de Funding, que añaden latencia sin mejorar la precisión en horizonte de 1-15 min.

---

## Execution Script

```bash
# Variables
BTC_SYM="BTC/USDT:USDT"
ETH_SYM="ETH/USDT:USDT"
BASE_URL="http://localhost:8080/api/actions/funding-action-server"

# ── PASO 1: Toxicidad (señal primaria) ─────────────────────────────────
curl -s -X POST "$BASE_URL/get-toxicity-index/run" \
  -H "Content-Type: application/json" \
  -d "{\"symbol\": \"$BTC_SYM\", \"ob_depth\": 20, \"trade_limit\": 500}" \
  > scalp_tox_btc.json &

curl -s -X POST "$BASE_URL/get-toxicity-index/run" \
  -H "Content-Type: application/json" \
  -d "{\"symbol\": \"$ETH_SYM\", \"ob_depth\": 20, \"trade_limit\": 500}" \
  > scalp_tox_eth.json &

wait

# ── PASO 2: Microstructure Audit (confirmación direccional) ─────────────
curl -s -X POST "$BASE_URL/microstructure-audit/run" \
  -H "Content-Type: application/json" \
  -d "{\"symbol\": \"$BTC_SYM\"}" \
  > scalp_audit_btc.json &

curl -s -X POST "$BASE_URL/microstructure-audit/run" \
  -H "Content-Type: application/json" \
  -d "{\"symbol\": \"$ETH_SYM\"}" \
  > scalp_audit_eth.json &

wait

# ── PASO 3: OB Walls D20 (mapa de landmines) ───────────────────────────
curl -s -X POST "$BASE_URL/get-ob-walls/run" \
  -H "Content-Type: application/json" \
  -d "{\"symbol\": \"$BTC_SYM\", \"depth\": 20}" \
  > scalp_walls_btc.json &

curl -s -X POST "$BASE_URL/get-ob-walls/run" \
  -H "Content-Type: application/json" \
  -d "{\"symbol\": \"$ETH_SYM\", \"depth\": 20}" \
  > scalp_walls_eth.json &

wait

echo "✅ FLOW-SCALP complete. Check: scalp_tox_*.json | scalp_audit_*.json | scalp_walls_*.json"
```

---

## Alpha-Trigger (Orden de ejecución)

```
[1] toxicity_index > 0.7      → Flujo informado activo
[2] AND absorption_rate > 0.5 → Institucionales están absorbiendo agresivamente  
[3] AND obi_20 > |0.40|       → Dirección confirmada (>0 = Long, <0 = Short)
[4] AND cvd_100_trades_usd ALIGNED con obi_20  → CVD positivo + OBI positivo = GO LONG
                                                   CVD negativo + OBI negativo = GO SHORT
[5] CHECK walls: el muro más cercano en dirección contraria debe estar > 0.3% de distancia
```

**Señal de entrada máxima confianza (PhD Tier):**
```
toxicity_index > 0.7 AND iceberg_score > 0.5 AND absorption_verdict == "ABSORBING_LONGS" AND cvd > 0
→ Institucionales comprando en silencio. Entry LONG inmediato.
```

---

## Decision Matrix

Ver `/flow-decision-matrix` para la tabla completa de interpretación y Risk-Flip.

**Quick Reference:**

| `toxicity_verdict` | `absorption_verdict` | `obi_20` | Acción |
|:---|:---|:---|:---|
| `TOXIC` | `ABSORBING_LONGS` | `> 0.40` | ✅ **GO LONG** |
| `TOXIC` | `ABSORBING_SHORTS` | `< -0.40` | ✅ **GO SHORT** |
| `ELEVATED` | `NEUTRAL` | `> 0.30` | 🟡 **WAIT 30s, re-scan** |
| `CLEAN` | any | any | ❌ **NO TRADE — retail soup** |
| any | any | `obi_20` flips sign | 🔴 **RISK-FLIP: ABORT** |
