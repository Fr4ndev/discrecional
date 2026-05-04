# 🏛️ CCXTV2 — Institutional Microstructure Intelligence Platform
![Version](https://img.shields.io/badge/Version-3.0_Consolidated-blue?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.10%2B-green?style=flat-square)
![Status](https://img.shields.io/badge/Status-Active_Production-orange?style=flat-square)

`ccxtv2` es una plataforma de inteligencia cuantitativa diseñada para detectar **flujos institucionales, absorción y anomalías de liquidez** en los mercados de BTC y ETH. Mediante un análisis profundo de microestructura (Order Book, CVD, Basis, Toxicity), el sistema identifica setups de alta convicción para trading institucional.

---

## 🏗️ 1. Arquitectura del Sistema (v3.0)

La arquitectura sigue una separación estricta de capas para garantizar la estabilidad y la integración con agentes de IA.

| Capa | Directorio | Responsabilidad | Componente Clave |
| :--- | :--- | :--- | :--- |
| **Core** | `core/` | Cerebro y Motor de Datos | `IntelligenceHub`, `RedisCache` |
| **Supervision** | `daemons/` | Monitoreo 24/7 | `GuardianDaemon`, `SFPMonitor` |
| **Action Server** | `funding_action_server/` | Interfaz REST para IA | `audit_actions.py`, `market_actions.py` |
| **Strategies** | `strategies/` | Lógica Cuantitativa | `zscore.py`, `spotdiff.py`, `ELE` |
| **Alerting** | `alerts/` | Notificaciones Unificadas | `SentinelGateway`, `telegram.py` |
| **Skills** | `skills/` | Biblioteca de Prompts | `microstructure-expert.md` |

---

## 🧠 2. God Nodes (Puntos Únicos de Verdad)

- **`IntelligenceHub`** (`core/Core_Intelligence_Hub.py`): El singleton central. Maneja conexiones CCXT, cálculos de métricas en tiempo real (OBI, CVD, Basis, Toxicity) y caché TTL con Redis.
- **`GuardianDaemon`** (`daemons/Guardian_Daemon.py`): El orquestador. Supervisa la salud de todos los daemons, gestiona reinicios automáticos y heartbeats.
- **`SentinelGateway`** (`alerts/gateway.py`): El hub de alertas. Centraliza, deduplica y encamina todas las notificaciones a Telegram.

---

## 🤖 3. Bot de Telegram (Centro de Mando)

El bot ahora opera en **modo bajo demanda** (manual) para evitar spam automático. Los comandos disponibles son:

### 📊 Análisis de Activos
- `/start` — Muestra el menú principal con todos los comandos.
- `/heatmap [ticker]` — Genera el mapa de calor S/R (ej: `/heatmap BTC`).
- `/orderflow [ticker]` — Análisis de flujo de órdenes y Wyckoff.
- `/spotdiff [ticker]` — Diferencial Spot vs Futures.
- `/zscore [ticker]` — Cálculo de Z-Score institucional.
- `/scan` — Escaneo rápido de todo el universo de activos.
- `/funding` — Tabla comparativa de Funding Rates multi-DEX.

### ⚡ Flujos de Auditoría Avanzada
Estos comandos ejecutan flujos de trabajo completos y devuelven el resultado final:
- `/turbo` — Snapshot global ultra-rápido de todo el mercado.
- `/scalp` — Auditoría de micro-tendencia (Toxicidad + Muros + OBI).
- `/intraday` — Captura de sesión (Basis + Confluencia + Niveles).
- `/sfp` — Búsqueda de patrones de reversión (Swing Failure Pattern).

---

## 🚀 4. Guía de Inicio Rápido

### Lanzamiento Manual
1. **Entorno:** `source venv/bin/activate`
2. **Servidor de Acciones:** `action-server start --port 8080 --dir funding_action_server`
3. **Bot de Telegram:** `python3 controller.py`

### Diagnóstico de Salud
Ejecuta el script de diagnóstico para asegurar que todo el stack está operativo:
```bash
./scripts/ops/status_check.sh
```

### Ejecución de Pruebas
Para validar la integridad del núcleo cuantitativo:
```bash
./scripts/ops/run_all_tests.sh
```
---

## 🔬 4. Métricas de Microestructura (PhD Level)

- **OBI (Order Book Imbalance)**: Mide la asimetría de liquidez. > 0.7 indica absorción de ventas.
- **CVD Acceleration (CVD'')**: Detecta ignición de momentum y barrido de niveles.
- **VPIN (Toxicity)**: Cuantifica el estrés de los market makers y la llegada de "Informed Flow".
- **Basis (Spot-Perp)**: Diferencial de precio. Clave para detectar acumulación real vs apalancamiento.
- **Wall Velocity**: Vector de movimiento de muros. Filtra Spoofing (muros fantasma).

---

## 🛠️ 5. Biblioteca de IA (Skills)

Ubicada en `skills/`, esta carpeta contiene guías expertas para que agentes de IA operen el sistema:
- **`architecture_reference.md`**: Mapa técnico para navegación.
- **`microstructure-expert.md`**: Interpretación de métricas complejas.
- **`trading-protocol-specialist.md`**: Protocolos para SFP y ELE (ETH Liquidity Engine).
- **`system-troubleshooter.md`**: Guía SRE para mantenimiento.
- **`graph_intelligence_map.md`**: Mapa de conectividad interna.

---

## 📂 6. Estructura de Datos y Logs

- **`data/snapshots/`**: Resultados JSON de todas las auditorías y flujos.
- **`data/charts/`**: Gráficos generados (PNG/SVG).
- **`data/*.log`**: Logs de actividad de daemons en tiempo real.
- **`logs/`**: Logs históricos y de telemetría ML.

---

## 📈 7. Roadmap & Mejora Continua (Vectores Criticos)
Basado en el análisis de grafos, los próximos pasos incluyen:
1. **Desacoplamiento Total**: Migrar dependencias de `DataEngine` hacia `IntelligenceHub` directo.
2. **Unificación de Alertas**: Enrutar el 100% de avisos a través de `SentinelGateway`.
3. **Optimización de WS**: Transición de polling REST a WebSockets para latencia <500ms.

---
**Disclaimer**: Proyecto de grado institucional. El trading conlleva riesgo. CCXTV2 es una herramienta de asistencia, no de ejecución automática sin supervisión.
