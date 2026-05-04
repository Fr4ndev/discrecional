# 🏛️ INTRADAY — Session Capture & Confluence
**Timestamp:** 2026-04-30 15:33:41 UTC
**Mode:** `intraday` | **VPIN:** `0.6269` | **OBI:** `0.6069` | **Basis:** `-0.0659%` | **Régimen:** `NEUTRAL`

---

# 📊 DOSSIER INSTITUCIONAL — INTRADAY SESSION CAPTURE
**Timestamp:** 2026-04-30 15:33:10 UTC  
**Analista:** Senior Desk — Microestructura Cripto  
**Framework:** FLOWS_OPERATING_MANUAL V2

---

## 🔍 DIAGNÓSTICO GLOBAL — Executive Summary

| Métrica | BTC | ETH | Umbral Crítico |
|:---|:---:|:---:|:---:|
| **VPIN (Toxicity)** | **0.6269** 🟡 | 0.5782 ❌ | > 0.62 |
| **OBI D20** | **-0.0998** ❌ | **-0.3199** ❌ | ±0.40 |
| **Basis %** | **-0.0313%** 🟢 | **-0.0701%** 🟢 | < -0.05% |
| **Z-Score m5** | 0.13 🟢 | 0.84 🟢 | ±1.5 |
| **Absorption Rate** | 32.78% ❌ | 27.28% ❌ | > 60% |
| **CVD Accel (100t)** | +272.7K 🟢 | +301.2K 🟢 | Positivo |
| **Kyle's Lambda** | 0.037 🟢 | 0.073 🟢 | < 0.10 |

**Veredicto Global:** 🟡 **MIXED — Partial Opportunity en BTC, ETH en espera**

---

## 🟡 BITCOIN — Análisis de Microestructura

### 📋 Tabla de Métricas vs Umbrales

| Métrica | Valor Actual | Umbral | Status | Señal |
|:---|---:|---:|:---:|:---|
| **VPIN** | 0.6269 | > 0.62 | ✅ | Informed Flow |
| **OBI D20** | -0.0998 | ±0.40 | ❌ | Neutro |
| **OBI Current** | +0.6069 | > +0.40 | ✅ | Presión Bid Spot |
| **Basis %** | -0.0313% | < -0.05% | 🟡 | Spot Premium leve |
| **Z-Score m5** | 0.13 | ±1.5 | 🟢 | Neutral |
| **Absorption** | 32.78% | > 60% | ❌ | Sin Icebergs activos |
| **CVD 100t** | +272.7K USD | Positivo | ✅ | Compra agresiva |
| **Kyle's Lambda** | 0.037 | < 0.10 | 🟢 | Mercado Deep |
| **Whale %** | 77.36% | > 60% | ✅ | Flujo institucional |

### 🔬 Interpretación de Confluencia

**VPIN 0.6269** — Supera el umbral mínimo de toxicidad. Flujo informado confirmado.  
**OBI Current +0.6069** vs **OBI D20 -0.0998** — **DIVERGENCIA CRÍTICA**: El OBI instantáneo muestra fuerte presión compradora en el book spot, pero el promedio de 20 ticks es neutro. Esto indica un **sweep direccional reciente** que aún no se ha consolidado en la microestructura.  
**Basis -0.0313%** — Spot Premium leve pero no extrema. No alcanza el umbral de -0.05% para acumulación stealth confirmada.  
**Absorption 32.78%** — Bajo. No hay icebergs absorbiendo oferta de forma agresiva.  
**CVD +272.7K** — Positivo y acelerando. Confirma que el flujo reciente es comprador.

### 🎯 SETUP — GO PARTIAL (Long Bias)

| Componente | Detalle |
|:---|---:|
| **Dirección** | 🟢 LONG (Cauteloso) |
| **Entry Zone** | **$76,400 - $76,500** (sobre OBI Current +0.60) |
| **Invalidación** | **$76,200** (pérdida del OBI Current positivo + VPIN < 0.60) |
| **Target 1** | **$76,800** (primer muro de resistencia) |
| **Target 2** | **$77,200** (extensión si Absorption > 40%) |
| **Sizing** | **50%** (GO PARTIAL — falta confirmación de Absorption) |
| **Timeframe** | 15-30 min |

**Razonamiento:**  
- VPIN > 0.62 + OBI Current +0.60 + CVD positivo = setup LONG válido  
- Pero OBI D20 neutro y Absorption baja = **no hay convicción para FULL**  
- El Basis no alcanza el umbral de acumulación stealth extrema  
- **Riesgo:** El sweep puede ser un fakeout si no se consolida el OBI D20

---

## ❌ ETHEREUM — Análisis de Microestructura

### 📋 Tabla de Métricas vs Umbrales

| Métrica | Valor Actual | Umbral | Status | Señal |
|:---|---:|---:|:---:|:---|
| **VPIN** | 0.5782 | > 0.62 | ❌ | Retail Soup |
| **OBI D20** | -0.3199 | ±0.40 | ❌ | Neutro |
| **OBI Current** | +0.1074 | > +0.40 | ❌ | Sin presión |
| **Basis %** | -0.0701% | < -0.05% | ✅ | Spot Premium confirmado |
| **Z-Score m5** | 0.84 | ±1.5 | 🟢 | Neutral |
| **Absorption** | 27.28% | > 60% | ❌ | Sin Icebergs |
| **CVD 100t** | +301.2K USD | Positivo | ✅ | Compra agresiva |
| **Kyle's Lambda** | 0.073 | < 0.10 | 🟢 | Mercado Deep |
| **Whale %** | 58.28% | > 60% | ❌ | Flujo mixto |

### 🔬 Interpretación de Confluencia

**VPIN 0.5782** — **NO SUPERA EL UMBRAL**. Flujo no informado. "Retail Soup" según el manual.  
**Basis -0.0701%** — Spot Premium confirmado. Acumulación stealth institucional presente.  
**OBI D20 -0.3199** — Neutro. No hay presión direccional en el book.  
**CVD +301.2K** — Positivo pero sin respaldo de VPIN ni OBI. **Divergencia peligrosa**.  
**Whale % 58.28%** — Por debajo del 60%. No hay dominio institucional claro.

### 🎯 SETUP — NO TRADE

| Componente | Detalle |
|:---|---:|
| **Dirección** | ❌ NO EXECUTION |
| **Razonamiento** | VPIN < 0.62 + OBI neutro = "Retail Soup" |
| **Excepción** | Basis -0.0701% sugiere acumulación stealth, pero sin VPIN ni OBI no se ejecuta |
| **Condición para re-evaluar** | VPIN > 0.62 + OBI D20 < -0.40 o > +0.40 |

**Razonamiento:**  
- El Basis extremo (-0.0701%) es tentador, pero el manual es claro: **VPIN < 0.62 = NO EXECUTION**  
- El CVD positivo sin VPIN ni OBI es **flujo retail no informado**  
- Esperar a que VPIN cruce 0.62 y OBI D20 muestre dirección

---

## 🚨 ALERTAS ESPECIALES

### 1. SFP Trigger en BTC — Tactical Scalp Activado
- **Max OBI registrado:** +0.8792 (sweep masivo)
- **Trigger Scalp:** ✅ ACTIVO
- **Análisis del Sweep:** El OBI instantáneo alcanzó +0.8792, indicando un barrido agresivo del lado bid. Sin embargo, el OBI D20 se mantiene en -0.0998, lo que sugiere que el sweep **no se ha consolidado** en la microestructura.
- **Calidad del Sweep:** 🟡 **MODERADA** — El volumen de CVD (+272.7K) respalda el movimiento, pero la falta de absorción (32.78%) y la no consolidación del OBI D20 indican que **el smart money no está comprometido** con este nivel.

### 2. Basis Divergencia en ETH
- **Basis -0.0701%** — Spot Premium confirmado en ETH
- **Interpretación:** Acumulación stealth institucional presente
- **Pero:** VPIN < 0.62 anula cualquier setup
- **Recomendación:** Monitorear para posible entrada si VPIN sube

### 3. Flujo Institucional en BTC
- **Whale % 77.36%** — Dominio institucional absoluto
- **Retail % 0.77%** — Casi nulo
- **Interpretación:** El mercado de BTC está siendo movido exclusivamente por flujo informado

---

## 📊 VEREDICTO GLOBAL

| Asset | Veredicto | Convicción | Setup |
|:---|---:|:---:|:---:|
| **BTC** | 🟡 GO PARTIAL | **MEDIA** | Long $76,400-$76,500 |
| **ETH** | ❌ NO TRADE | **BAJA** | Esperar VPIN > 0.62 |

### Resumen de Confluencia:
- **VPIN:** Solo BTC supera el umbral (0.6269)
- **OBI:** Ambos neutros en D20, aunque BTC muestra presión spot
- **Basis:** Ambos en Spot Premium, ETH más extremo
- **Absorption:** Ambos bajos — sin icebergs activos
- **CVD:** Ambos positivos — flujo comprador general

### Riesgo Principal:
- **Falta de consolidación del OBI D20 en BTC** — el sweep puede ser un fakeout
- **VPIN bajo en ETH** anula el setup a pesar del Basis extremo
- **Absorption baja en ambos** — sin soporte de smart money en los muros

---

**CONVICTION LEVEL: MEDIO**  
*Setup parcial en BTC con stops ajustados. ETH en espera hasta que VPIN confirme el flujo informado. El mercado muestra señales mixtas: flujo institucional en BTC pero sin consolidación, acumulación stealth en ETH pero sin toxicidad. Disciplina de ejecución: solo setups con VPIN > 0.62 + OBI confirmado.*

---
*Generado por auto_senior_analyst.py | CCXTV2 Unified Intelligence | DeepSeek deepseek-chat*
