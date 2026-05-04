# 🧠 Institutional Intelligence: Senior Desk Operating Manual (V2)
**Proprietary Microstructure & Order Flow Execution Framework**

Este manual define los protocolos de auditoría de alta precisión para el Senior Desk, utilizando el `funding-action-server` como motor de ejecución táctica. El objetivo es la captura de Alpha mediante la detección de flujos informados, absorción institucional y desequilibrios de liquidez.

---

## 🏎️ 1. Rutina Maestra: /turbo-all (Executive Summary)
**Propósito:** Diagnóstico holístico de la salud del mercado en < 60 segundos.
**Veredicto:** Determina el sesgo direccional de la sesión.

### 📊 Decision Matrix: Global Health
| Métrica | Requisito BULLISH | Requisito BEARISH | Risk-Flip (Abort) |
| :--- | :--- | :--- | :--- |
| **Z-Score Funding** | < -2.0 (Deep Discount) | > 2.0 (Overheated) | Reversión a Mean (0) |
| **Avg OBI (20)** | > +0.35 | < -0.35 | Flip de signo instantáneo |
| **OI Delta (30m)** | > +5% (Aggressive Acc) | > +5% (Aggressive Dist) | Caída de OI con precio plano |
| **Basis Divergence** | Negative (Spot Leading) | Positive (Perp FOMO) | Gap Closing (Fair Value) |

---

## ⚡ 2. /flow-scalp (Micro-Trend Explosion)
**Propósito:** Captura de movimientos de alta frecuencia (1-15 min) mediante VPIN y Icebergs.
**Frecuencia:** Ejecución continua durante ventanas de alta volatilidad.

### 🧩 Decision Matrix: Scalp Execution
| Métrica | Señal LONG | Señal SHORT | Risk-Flip |
| :--- | :--- | :--- | :--- |
| **Toxicity (VPIN)** | > 0.62 (Informed) | > 0.62 (Informed) | < 0.40 (Retail Noise) |
| **Muro de Berlín** | **Toxicity < 0.62** | **"Retail Soup"** | **NO EXECUTION** |
| **Absorption Rate** | > 0.60 (Icebergs Bid) | > 0.60 (Icebergs Ask) | Score -> 0 (Wall Pulling) |
| **OBI D20** | > +0.40 | < -0.40 | Muro barrido s/ seguimiento |
| **CVD Accel** | Positive Acceleration | Negative Acceleration | Decaimiento de Momentum |

---

## 📅 3. /flow-intraday (Session Capture)
**Propósito:** Localización de niveles institucionales de 'Floor' y 'Ceiling' y validación de Lead/Lag.

### 🎯 Decision Matrix: Intraday Pivot
| Métrica | Sesgo BULLISH | Sesgo BEARISH | Risk-Flip |
| :--- | :--- | :--- | :--- |
| **Basis Premium** | Basis < -0.05% (Spot) | Basis > +0.05% (Perp) | Basis -> 0.00% (Neutral) |
| **Suelo de Spot** | **Basis < -0.05%** | **Invalida SHORTS** | **Accumulation Stealth** |
| **Confluence Score** | > 75 (High Resolve) | > 75 (High Resolve) | < 45 (Mixed Signals) |
| **UD Walls (D100)** | Bids > $10M @ Support | Asks > $10M @ Resist | Desaparición del muro (Ghost) |
| **SFP Trigger** | Sweep Daily Low | Sweep Daily High | Reclamo fallido del nivel |

---

## 🌊 4. /flow-swing (Regime Change)
... [existing content] ...

---

## 🏛️ 5. Capa HTF: ELITE Z-SCORE (The Macro Guard)
**Propósito:** Definir si estamos operando a favor o en contra del ciclo institucional de largo plazo.

### 📊 HTF Interpretation Grid
| Timeframe | Condición | Veredicto Macro | Impacto en Estrategia |
| :--- | :--- | :--- | :--- |
| **1M (Mensual)** | Score < 40 | **Short Premium** | Solo Longs tipo Scalp. TP rápido. |
| **1M (Mensual)** | Score > 60 | **Long Premium** | Compras institucionales de fondo. |
| **1D (Diario)** | Score > 80 | **Accumulation** | Sesgo Intraday fuertemente alcista. |
| **1D (Diario)** | Score < 20 | **Distribution** | Sesgo Intraday fuertemente bajista. |

---

## 🛰️ 6. /flow-alpha-sentinel (The Hybrid Master)

**Propósito:** El "Veredicto Definitivo". Máxima confluencia multi-horizonte.

**Alineación Direccional:** Se define cuando las tres capas (Scalp, Intraday, Swing) coinciden en el sesgo (Ej. Todas Bullish).

### 🏆 Alpha Trigger Levels (Multi-Weight Calibration)
| Nivel de Convicción | Requisitos Técnicos | UD Confluence Weight | Sizing | Acción |
| :--- | :--- | :--- | :--- | :--- |
| **NO SIGNAL** | Toxicity < 0.62 | 0% | 0.0x | Standby (Soup) |
| **MODERATE** | 2 Capas + OBI > |0.30| | > 50% | 0.5x | Scalp |
| **HIGH CONVICTION** | 3 Capas + Toxicity > 0.65 | > 75% | 1.0x | Entry |
| **MAX CONVICTION** | 3 Capas + Tox > 0.75 + Basis Ext | > 90% | 1.5x - 2.0x | **FULL SEND** |

---

## 🛰️ 6. Protocolo: Ignition Bridge (BTC-ETH Divergence)
**Contexto:** Observamos que ETH suele mostrar OBI positivo antes que BTC (Alpha Rotation), pero BTC es quien dispara la ignición final.

1.  **Stealth Phase (ETH):** Si ETH tiene Basis < -0.05% y OBI > 0.35, pero BTC sigue ruidoso -> **MONITOR ONLY**. No entrar en el "segundo" sin el líder.
2.  **Ignition Phase (BTC):** Cuando BTC cruza Toxicity > 0.62 y OBI > 0.40 -> **LONG LÍDER**. 
3.  **The Bridge (Aggression Trigger):**
    *   Solo entrar en ETH cuando su Toxicity se alinee (> 0.62) **Y** el `CVD Acceleration` (CVD'') sea positivo. Esto confirma que el flujo informado ha pasado de compra pasiva (limit) a barrido de liquidez (market aggression).
4.  **Symmetry Check:** Si la rotación está en curso pero BTC muestra una re-ignición (Toxicity > 0.70), pausar la entrada en ETH. BTC sigue siendo el ancla; su expansión incompleta puede generar correlación negativa temporal o sacudidas en ETH.

---

## ⚠️ Risk & Position Sizing Rules
1.  **Fixed Multiplier:** Nunca exceder el sizing sugerido por el Alpha Trigger Level.
2.  **Risk-Flip Stop:** Si el flujo primario (/flow-scalp) entra en Risk-Flip (Toxicity cae < 0.40 o OBI flipea), cerrar **50% de la posición** a mercado inmediatamente.
3.  **Invalidación Técnica:** Si el precio cruza el muro institucional detectado en UD-Confluence, cerrar el **100%**.
4.  **Anti-Slippage:** Trades de **MAX CONVICTION** deben ejecutarse mediante TWAP o algoritmos de ejecución pasiva si el VPIN es > 0.80 para evitar impacto.

---

## 🏛️ 7. Protección Predatoria: Liquidity-Aware SL
**Protocolo de defensa para evitar sacudidas (wick-protection) en entornos de alta volatilidad.**

1.  **SL Basado en UDC:** El Stop Loss se ancla dinámicamente **2 ticks por debajo** del muro institucional (Bids) más profundo detectado por el motor `get-ultra-deep-confluence`.
2.  **Filtro de Volatilidad (Tox-Expansion):**
    *   Si `Toxicity > 0.70`, el sistema amplía automáticamente el margen del SL un **15%** (Buffer de Ignición). Esto evita que el ruido retail previo a la rotura real nos saque de la posición.
3.  **Aggressive Breakeven:** Una vez que el precio avanza `1.5x` el deslizamiento real de entrada (`slippage_real`), el SL se mueve a **Breakeven (Entry Price)** de forma atómica.

---

## 🛠️ Execution & Automation (Curl Commands)

### /run_flows.sh Usage
El script automatiza las llamadas concurrentes para minimizar la latencia de datos.

```bash
# Ejemplo: Iniciar auditoría de máxima convicción
./run_flows.sh alpha
```

### Manual Commands (Power User)
```bash
# Auditoría de Microestructura Individual
curl -s -X POST "http://localhost:8080/api/actions/funding-action-server/microstructure-audit/run" \
     -H "Content-Type: application/json" \
     -d '{"symbol": "BTC/USDT:USDT"}'

```bash
# Escaneo de Toxicidad Crítico (VPIN)
curl -s -X POST "http://localhost:8080/api/actions/funding-action-server/get-toxicity-index/run" \
     -H "Content-Type: application/json" \
     -d '{"symbol": "ETH/USDT:USDT", "ob_depth": 20, "trade_limit": 1000}'
```

---

## 🚀 Estrategias Avanzadas: Institutional Microstructure

### [A] The "Shark in the Water" Squeeze
**Setup:** Toxicity > 0.68 + Basis < -0.08% + OBI > 0.50.
**Lógica:** Captura el momento exacto en que los shorts retail son forzados a cubrir contra una demanda spot institucional implacable.
**Acción:** Market Buy agresivo + SL @ UD-Support Level.

### [B] Informed Divergence (The Stealth Trap)
**Setup:** ETH OBI < -0.40 + ETH Basis < -0.05% + BTC Toxicity > 0.62.
**Lógica:** Los institucionales mantienen el Spot Premium en ETH mientras el libro de scalp engaña al retail con sesgo bajista (Spoofing/Retail Panic).
**Acción:** Ignorar el OBI bajista de ETH. Buscar entrada larga en la rotación de BTC.

### [C] Wall Velocity Fix (Anti-Spoofing)
**Nota:** Requiere **Redis ONLINE**. Sin Redis, el sistema no puede calcular la velocidad de los muros (Vw) vs la del precio (Vp).
**Verificación:** `curl http://localhost:8080/api/actions/funding-action-server/check-infra` para asegurar `redis: OK`.
