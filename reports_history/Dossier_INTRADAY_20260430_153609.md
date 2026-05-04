# 🏛️ INTRADAY — Session Capture & Confluence
**Timestamp:** 2026-04-30 15:36:09 UTC
**Mode:** `intraday` | **VPIN:** `0.6836` | **OBI:** `0.1733` | **Basis:** `-0.0336%` | **Régimen:** `NEUTRAL`

---

# 📊 INFORME INTRADAY — Session Capture & Confluence
**Timestamp:** 2026-04-30 15:35:40 UTC  
**Analista:** Senior Desk — Microestructura Institucional

---

## 🔍 DIAGNÓSTICO GLOBAL — Executive Summary

| Métrica | BTC | ETH | Umbral Crítico |
|:---|:---:|:---:|:---:|
| **VPIN (Toxicity)** | 0.6836 🟡 | 0.6541 🟡 | > 0.62 ✅ |
| **OBI D20** | **-0.6296** 🔴 | **-0.0098** ⚪ | ±0.40 |
| **Basis %** | **-0.0536%** 🟢 | **-0.0476%** 🟢 | < -0.05% |
| **Absorption Rate** | -29.69 ⚪ | -32.43 ⚪ | > 0.60 |
| **Iceberg Score** | 0.0389 (ASK) | 0.0016 (ASK) | — |
| **CVD (100 trades)** | -$45,244.88 🔴 | — | Negativo |
| **Kyle's Lambda** | 0.0776 🟢 | 0.0582 🟢 | < 0.10 = DEEP |
| **Whale Flow %** | 65.57% 🐋 | 73.49% 🐋 | > 60% |
| **Z-Score m5** | -0.45 ⚪ | — | ±1.5 |

**Veredicto Global:** 🟡 **MIXED — Sesgo Bearish en BTC, Neutro en ETH**

---

## 🟠 BITCOIN (BTC/USDT:USDT) — Análisis Detallado

### Tabla de Métricas vs Umbrales

| Métrica | Valor Actual | Umbral | Status | Señal |
|:---|---:|---:|:---:|:---:|
| VPIN | 0.6836 | > 0.62 | ✅ | Informed Flow |
| OBI D20 | **-0.6296** | < -0.40 | ✅ | **Bearish Pressure** |
| Basis % | -0.0536% | < -0.05% | ✅ | **Spot Premium (Accumulation)** |
| Absorption Rate | -29.69 | > 0.60 | ❌ | NEUTRAL |
| Iceberg Score | 0.0389 (ASK) | > 0.60 | ❌ | No Icebergs |
| CVD Accel | -$45,244.88 | Negativo | ✅ | Selling Pressure |
| Z-Score m5 | -0.45 | ±1.5 | ⚪ | Neutral |
| Kyle's Lambda | 0.0776 | < 0.10 | 🟢 | Deep Market |

### Interpretación Institucional

**CONFLUENCIA PARCIAL — Sesgo Bearish Confirmado**

1. **VPIN 0.6836** → Flujo informado activo. No es ruido retail.
2. **OBI D20 = -0.6296** → Presión vendedora institucional masiva en el order book. Supera el umbral de -0.40.
3. **Basis -0.0536%** → Spot Premium. Acumulación stealth en spot, pero el perp está siendo vendido agresivamente.
4. **CVD negativo (-$45K)** → Confirma la dirección del OBI. Venta activa en el perp.
5. **⚠️ DIVERGENCIA CRÍTICA:** Basis indica acumulación spot, pero OBI + CVD muestran presión bajista en perp. Esto sugiere **distribución institucional** — están vendiendo el perp mientras acumulan spot para cubrir.

### Decisión: 🟡 GO PARTIAL — SHORT BIAS

| Componente | Señal | Peso |
|:---|---:|---:|
| VPIN | ✅ | 25% |
| OBI | ✅ Bearish | 30% |
| Basis | ✅ Accumulation (conflicto) | 15% |
| CVD | ✅ Bearish | 20% |
| Absorption | ❌ Neutro | 10% |

**Convicción:** MEDIA — La divergencia Basis vs OBI/CVD reduce la confianza.

### SETUP — SHORT SCALP (Intraday)

| Parámetro | Valor |
|:---|---:|
| **Entry** | $76,450 - $76,500 (actual) |
| **Invalidation** | $76,800 (cierre sobre OBI D20 > -0.30) |
| **Target 1** | $76,000 |
| **Target 2** | $75,800 |
| **Stop Loss** | $76,850 |
| **Sizing** | 0.5x (Partial) |
| **Timeframe** | 15-30 min |

---

## 🟠 ETHEREUM (ETH/USDT:USDT) — Análisis Detallado

### Tabla de Métricas vs Umbrales

| Métrica | Valor Actual | Umbral | Status | Señal |
|:---|---:|---:|:---:|:---:|
| VPIN | 0.6541 | > 0.62 | ✅ | Informed Flow |
| OBI D20 | **-0.0098** | ±0.40 | ❌ | **BALANCED** |
| Basis % | -0.0476% | < -0.05% | ❌ | **Borderline** |
| Absorption Rate | -32.43 | > 0.60 | ❌ | NEUTRAL |
| Iceberg Score | 0.0016 (ASK) | > 0.60 | ❌ | No Icebergs |
| CVD (total) | -$1,621,346 | Negativo | ✅ | Selling Pressure |
| Whale Flow % | 73.49% | > 60% | ✅ | Institutional Dominance |
| Kyle's Lambda | 0.0582 | < 0.10 | 🟢 | Deep Market |

### Interpretación Institucional

**SIN CONFLUENCIA — Mercado Neutro con Ruido de Fondo**

1. **VPIN 0.6541** → Flujo informado, pero sin dirección clara.
2. **OBI D20 = -0.0098** → Order book perfectamente balanceado. Sin presión direccional.
3. **Basis -0.0476%** → Spot Premium borderline. No alcanza el umbral de -0.05%.
4. **CVD masivo negativo (-$1.62M)** → Venta significativa en el perp, pero el OBI no lo refleja. Posible liquidación o flujo de una sola ballena.
5. **Whale Flow 73.49%** → Dominio institucional absoluto. El mercado está en manos de grandes players.

### Decisión: ❌ NO TRADE

| Componente | Señal | Peso |
|:---|---:|---:|
| VPIN | ✅ | 25% |
| OBI | ❌ Neutro | 30% |
| Basis | ❌ Borderline | 15% |
| CVD | ✅ Bearish (sin confirmación OBI) | 20% |
| Absorption | ❌ Neutro | 10% |

**Convicción:** BAJA — OBI neutro invalida cualquier setup direccional.

---

## 🔄 ANÁLISIS DE DIVERGENCIAS CRÍTICAS

### BTC: Basis vs OBI/CVD
```
Basis: -0.0536% → Spot Premium (Acumulación)
OBI:  -0.6296  → Presión Vendedora
CVD:  -$45K    → Venta Activa
```
**Interpretación:** Los institucionales están **distribuyendo**. Venden el perp agresivamente mientras acumulan spot. Esto es típico de distribución en rango alto. Señal bajista de mediano plazo.

### ETH: CVD vs OBI
```
CVD: -$1.62M → Venta Masiva
OBI: -0.0098  → Order Book Balanceado
```
**Interpretación:** El CVD negativo masivo sin reflejo en OBI sugiere un **evento puntual** (liquidación, swap, OTC block trade). No es flujo orgánico direccional. Ignorar para scalping.

---

## 📋 RESUMEN DE SETUPS

| Asset | Decisión | Entry | Invalidation | Targets | Convicción |
|:---|---:|---:|---:|---:|---:|
| **BTC** | 🟡 GO PARTIAL SHORT | $76,450-500 | $76,800 | $76,000 / $75,800 | MEDIA |
| **ETH** | ❌ NO TRADE | — | — | — | BAJA |

---

## 🧠 VEREDICTO GLOBAL

| Componente | Status |
|:---|---:|
| **Toxicidad General** | 🟡 Elevada — Flujo informado presente |
| **Sesgo Direccional** | 🔴 Ligeramente Bearish (solo BTC) |
| **Calidad de Setup** | 🟡 Parcial — Divergencias reducen convicción |
| **Riesgo de Slippage** | 🟢 Bajo — Kyle's Lambda profundo en ambos |
| **Ventana de Ejecución** | 🟡 15-30 min — Scalping táctico |

### Recomendación Final
- **BTC:** Short parcial con stops ajustados. La divergencia Basis vs OBI/CVD es riesgosa para posiciones grandes.
- **ETH:** Mantenerse al margen. El OBI neutro anula cualquier setup a pesar del VPIN elevado.
- **Monitorear:** Si OBI D20 de BTC se profundiza por debajo de -0.70 con CVD acelerando, considerar aumentar sizing a FULL.

---

**CONVICTION LEVEL: MEDIO**  
*Próximo check: 15:45 UTC — Re-evaluar OBI D20 y CVD Accel en BTC.*

---
*Generado por auto_senior_analyst.py | CCXTV2 Unified Intelligence | DeepSeek deepseek-chat*
