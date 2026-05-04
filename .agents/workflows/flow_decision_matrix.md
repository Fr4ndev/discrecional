---
description: "Master Decision Matrix — Skill de Interpretación para Flow-Scalp, Flow-Intraday y Flow-Swing"
---

# 🧠 FLOW DECISION MATRIX — Senior Desk Interpretation Skill (Adaptive 1.1)

Este archivo es la referencia maestra que Antigravity usa para interpretar los JSON devueltos por los flujos especializados. Incluye la capa **HTF ELITE Z-SCORE**.

---

## 🏆 CAPA 0: HTF ELITE Z-SCORE (Contexto Macro)
**Archivos**: `zscore_elite_{asset}.json`

| Timeframe | Score Bullish | Score Bearish | Significado |
| :--- | :--- | :--- | :--- |
| **1M (Mensual)** | > 60 | < 40 | Régimen de Largo Plazo (Inversionista) |
| **1W (Semanal)** | > 70 | < 30 | Ciclo de Mercado (Posicionamiento Ballena) |
| **1D (Diario)** | > 80 | < 20 | Sesgo de Swing (Tendencia Semanal) |

**REGLA DE ORO HTF:**
- Si **1M Score < 40**, el mercado está en **"Short Premium"**. Cualquier Long en timeframes menores es un contra-tendencia macro (Scalp únicamente).
- Si **1M Score > 60**, el mercado está en **"Accumulation Floor"**. Los Shorts son trampas de liquidez retail.

## 🏛️ HISTORIAL & ESTRATEGIA AVANZADA
- **Reportes:** Ver `reports_history/` para auditorías pasadas.
- **Estrategia Dual-Regime:** Consultar `DUAL_REGIME_STRATEGY.md` para setups de divergencia HTF (Monthly vs Daily).

---

## 🔬 FLOW-SCALP Decision Matrix (Calibración NY Open)
... [rest of scalp matrix] ...

---

## ⚡ Cross-Flow Escalation Logic (HTF Filtered)

```
# Filtro de Convicción Macro
IF zscore_elite_btc["1M"]["score"] < 40:
   REDUCIR TAMAÑO DE LONGS EN -50% (Régimen de Distribución Mensual)
   AUMENTAR TAMAÑO DE SHORTS EN +20% (Alineación con Smart Money HTF)

IF flow-scalp dispara (score ≥ 7) Y flow-intraday confirma:
   → ESCALAR de scalp a intraday SIEMPRE QUE 1D Score > 50.
```

**Archivos de entrada**: `scalp_tox_{asset}.json` | `scalp_audit_{asset}.json` | `scalp_walls_{asset}.json`

### Campo → Significado → Umbral Accionable

| Campo JSON | Ruta exacta | Bullish Signal | Bearish Signal | Abort (Risk-Flip) |
|:---|:---|:---|:---|:---|
| `toxicity_index` | `.toxicity.index` | `> 0.60` | `> 0.60` (+ short OBI) | Cae a `< 0.40` en < 30s |
| `absorption_verdict` | `.absorption.verdict` | `"ABSORBING_LONGS"` | `"ABSORBING_SHORTS"` | `"NEUTRAL"` repentino |
| `iceberg_score` | `.iceberg.score` | `> 0.40` | `> 0.40` (+ short dir) | Cae a `0.0` → muro retirado |
| `obi_20` | `.microstructure.obi_20` | `> +0.35` | `< -0.35` | Cambio de signo |
| `cvd_100_trades_usd` | `.microstructure.cvd_100_trades_usd` | `> 0` + OBI+  | `< 0` + OBI- | CVD vs OBI discordantes |
| `basis_pct` | `.microstructure.basis_pct` | `< 0` (Spot lider) | `> 0` (Perp lider) | Basis cruza `0` bruscamente |
| `zscore_m5` | `.microstructure.zscore_m5` | `-1.5 < z < 1.5` | idem | `abs(z) > 2.5` (exhaustion) |

### Scalp Composite Score (Adaptive 1.0)

```
score = 0
if toxicity.index > 0.60: score += 3  
if abs(obi_20) > 0.35:    score += 3  
if iceberg.score > 0.40:  score += 2  
if cvd ALIGNED con OBI:   score += 2
if basis < 0 (para longs) or > 0 (para shorts): score += 1

RESULTADO:
  score >= 7  → GO (Umbral optimizado para volatilidad actual)
  score 5-6   → GO PARTIAL (mitad de tamaño)
  score < 5   → WAIT o NO TRADE
```

---

## ⚡ Conflict Resolution & Informed Divergence

Si las métricas entran en conflicto, aplicar estas reglas de desempate:

**1. Informed Divergence (The Stealth Phase):**
- **Condición**: `toxicity.index > 0.75` PERO `abs(obi_20) < 0.20`.
- **Interpretación**: Los traders informados están acumulando en secreto sin mover el libro (Icebergs). 
- **Acción**: MONITOR_URGENT (re-scan cada 10s). Preparar entrada en el primer "OBI Snap" > 0.30.

**2. Toxic Fakeout (The Retail Trap):**
- **Condición**: `abs(obi_20) > 0.60` PERO `toxicity.index < 0.30`.
- **Interpretación**: Un lado del libro pesa mucho pero el flujo no es "inteligente". Es probable que sea una pared retail o spoofing detectado por el motor.
- **Acción**: NO TRADE. Esperar a que la toxicidad suba.

**3. Basis Discordance:**
- **Condición**: OBI y CVD son alcistas, pero `basis_pct` es positivo (Perp Premium).
- **Interpretación**: El movimiento está liderado por FOMO de retail (Perps) y no por acumulación genuina de Spot. Baja probabilidad de extensión.
- **Acción**: SCALP_ONLY. Take profit agresivo en TP1.

**4. Sincronización de Delta (Divergence Block):**
- **Condición**: `toxicity.index > 0.60` PERO existe divergencia delta severa entre exchanges (ej. Binance CVD > 0, OKX CVD < 0 con >50% de diferencia neta).
- **Interpretación**: No hay consenso institucional. Un jugador grande está atrapando a otro, o hay arbitraje sucio.
- **Acción**: BLOQUEO TOTAL. No entrar hasta que el CVD global se alinee en la misma dirección. (Evita comerse el impacto del rebalaceo).

**5. Safe Haven Rotation (Alpha Transfer):**
- **Condición**: `BTC_Toxicity > 0.70` (Tóxico/Distribución) Y `ETH_OBI > 0.50` (Acaparamiento).
- **Interpretación**: El "Smart Money" está rotando liquidez agresivamente desde BTC hacia ETH. El ecosistema usa ETH como Safe Haven de parking institucional.
- **Acción**: Aumentar el +40% de "Weight" (tamaño) a las señales largas en ETH. Ignorar temporalmente la matriz de correlación tradicional direccional con BTC.

---

## 📊 FLOW-INTRADAY Decision Matrix

| `basis_pct` | `confidence_score` | `direction` (UDC) | `max_obi` (táctico) | Acción |
|:---|:---|:---|:---|:---|
| `< -0.03%` | `≥ 50` | `LONG_BIAS` | `> 0.35` | ✅ **GO LONG — intraday** |
| `> +0.05%` | `≥ 50` | `SHORT_BIAS` | `< -0.35` | ✅ **GO SHORT — intraday** |
| any | any | any | OBI flips sign | 🔴 **RISK-FLIP: ABORT** |

---

## 🏗️ FLOW-SWING Decision Matrix

| `trigger_conservative` | `basis_pct` | `trigger_swing` | `max_abs_zscore` | Acción |
|:---|:---|:---|:---|:---|
| `True` | `< -0.03%` | `True` | `> 2.0` | ✅ **GO LONG SWING** |
| `False` | neutral | `False` | `< 1.5` | ❌ **NO TRADE** |

---

## ⚡ Cross-Flow Escalation Logic

```
IF flow-scalp dispara (score ≥ 7) Y flow-intraday también confirma (confluence_pct ≥ 70%):
   → ESCALAR de scalp a intraday. Mantener con SL en breakeven.

IF flow-swing da ABORT (trigger_conservative pasa a False):
   → CERRAR TODO.
```

---

## 🔴 Auto-Kill Switch (Exit-All Protocol)

Nivel crítico de intervención donde el sistema ordena **Liquidación a Mercado** de todas las posiciones (Scalp, Intraday, Swing) sin importar el PnL actual.

- **Condición**: `toxicity.index < 0.25` Y `liquidation_intensity > 0.70` en dirección CONTRARIA a la posición.
- **Interpretación**: Los institucionales han abandonado totalmente el mercado. El libro de órdenes quedó en poder exclusivo de retail, e inicia un evento de liquidación en cadena violento contra la posición. El nivel ya no protegerá el "Floor/Ceiling".
- **Acción**: `EXIT_ALL_POSITIONS_MARKET` inmediatamente. No esperar a re-testing del nivel de invalidación.

---

## 🚀 Deployment Quick-Reference


| Comando | Flujo |
|:---|:---|
| `/flow-scalp` | Scalp bursts, toxicity scans |
| `/flow-intraday` | Session floor/ceiling |
| `/flow-swing` | Regime audit, OI history |
