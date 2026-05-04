# 🏛️ CCXTV2 — System Architecture v3.0
**Institutional Microstructure Intelligence Platform**

**Fecha:** 28 Abril 2026  
**Versión:** 3.0 (Consolidada)  
**Estado:** Producción Activa

---

## 1. Executive Summary

`ccxtv2` es una plataforma especializada en **análisis de microestructura** para BTC y ETH. Su objetivo principal es detectar flujos institucionales, absorción, spoofing y oportunidades de alta convicción mediante el monitoreo en tiempo real de OBI, CVD, Basis, Toxicity y patrones SFP.

La arquitectura sigue el principio de **separación clara de responsabilidades**, lo que permite escalabilidad, mantenibilidad y fácil integración con agentes IA.

---

## 2. Arquitectura por Capas

### 1. Core Layer (`core/`) — El Cerebro

**Responsabilidad:** Centralizar datos, caché y cálculos cuantitativos de alto nivel.

**Componentes clave:**

- **`Core_Intelligence_Hub.py`** → `IntelligenceHub` (Singleton principal)
  - Punto único de verdad del sistema
  - Manejo de conexiones CCXT (Spot + Futures)
  - TTL Cache + Redis integration
  - Cálculo de todas las métricas PhD (OBI, CVD, Toxicity, Basis, Wall Velocity, etc.)

- **`data_engine.py`** → Shim de compatibilidad (Backward Compatible)
  - Mantiene funcionando código legacy sin romperlo

- Otros módulos: `config.py`, `execution_engine.py`, `redis_cache.py`, `indicators.py`, `visualizer.py`, `telemetry.py`

---

### 2. Supervision Layer (`daemons/`) — El Guardián

**Responsabilidad:** Monitoreo continuo 24/7 y orquestación de tareas.

**Componentes clave:**

- **`Guardian_Daemon.py`** → **Orquestador central del sistema**
  - Supervisor de todas las tareas sentinel
  - Gestión de lifecycle, auto-restart y heartbeat
  - Puente entre SignalBus y SentinelGateway

- **`sfp_advanced_monitor.py`** → Motor avanzado de Swing Failure Pattern (SFP v2.2)
- **`level_break_alert.py`** → Detección de rupturas y rechazos de niveles clave

---

### 3. Action Server Layer (`funding_action_server/actions/`) — Interfaz para Agentes

**Responsabilidad:** Proporcionar endpoints REST estables para análisis on-demand.

**Archivos principales:**

- `audit_actions.py` — Audits profundos (microstructure, ELE, senior desk)
- `market_actions.py` — Métricas en tiempo real (walls, basis, toxicity, etc.)
- `absorption_detector.py` — Detector avanzado de absorción institucional
- `funding_actions.py` — Funding rates multi-DEX y estado de mercado

**Nota:** Esta capa está **intencionalmente aislada** porque corre en proceso separado (Sema4.ai Action Server).

---

### 4. Strategies Layer (`strategies/`) — Motores Tácticos

**Responsabilidad:** Análisis cuantitativo y generación de señales visuales/tácticas.

**Archivos principales:**

- `funding_fees.py`
- `zscore.py` + `zscore_chart.py`
- `spotdiff.py` + `spotdiff_chart.py`
- `heatmap.py`
- `eth_liquidity_engine.py`
- `orderflow.py`

---

### 5. Alerting Layer (`alerts/`) — Sistema Unificado de Notificaciones

**Responsabilidad:** Centralizar todas las alertas del sistema.

**Componentes:**

- **`gateway.py`** → `SentinelGateway` (Punto único recomendado)
  - Priority queue, deduplicación, rate limiting
- `telegram.py` → Wrapper ligero (debería delegar en SentinelGateway)

**Recomendación actual:** Unificar **todo** el envío a Telegram a través de `SentinelGateway`.

---

### 6. Interface Layer

- `controller.py` → Bot de Telegram (comandos interactivos)
- `ml_dashboard.py` → Dashboard de observabilidad

---

## 3. God Nodes Principales

| Nodo                        | Capa              | Rol Principal                        | Recomendación |
|----------------------------|-------------------|--------------------------------------|-------------|
| `IntelligenceHub`          | Core              | Cerebro central del sistema          | Mantener como Singleton |
| `GuardianDaemon`           | Supervision       | Orquestador y supervisor 24/7       | Núcleo operativo |
| `DataEngine`               | Core              | Shim de compatibilidad               | Reducir uso progresivamente |
| `SentinelGateway`          | Alerting          | Punto único de alertas               | Unificar Telegram aquí |
| `SFPAdvancedMonitor`       | Supervision       | Detección avanzada de SFP            | Mantener |

---

## 4. Recomendaciones de Consolidación

1. **Unificar Telegram** → Todo debe pasar por `SentinelGateway`
2. **Migrar imports** → Reemplazar gradualmente `DataEngine` por `IntelligenceHub` directo
3. **Completar Event Bus** (`core/bus/`)
4. **Organizar scripts** → Consolidar `.sh` bajo `run_flows.sh`
5. **Crear carpeta `skills/`** para prompts y skills de IA

---

## 5. Flujo General de Datos

```mermaid
graph TD
    Exchanges --> IntelligenceHub
    IntelligenceHub --> GuardianDaemon
    GuardianDaemon --> SentinelGateway
    GuardianDaemon --> Strategies
    Strategies --> ActionServer
    ActionServer --> IntelligenceHub
    SentinelGateway --> Telegram
    controller.py --> ActionServer
