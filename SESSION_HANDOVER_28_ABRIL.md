# 📝 Handover Notes — CCXTV2 Senior Desk (28 Abril 2026)

## 🚀 Cambios Implementados

### 1. WhaleMonitor v3.0 (Grado Institucional)
- **Ventanas Fijas (Fixed Blocks):** Se cambió de ventanas deslizantes a bloques de 30s no solapados para eliminar señales duplicadas y contradictorias.
- **Lógica Anti-Flip-Flop:** Implementado un filtro de cambio de régimen que bloquea alertas opuestas en menos de 60s, a menos que el volumen sea > 2.5x el anterior.
- **Niveles de Alerta:**
    - `LARGE`: Flujos significativos (33% del umbral Whale).
    - `WHALE`: Movimientos institucionales reales (Umbrales: BTC $750k, ETH $1.1M, SOL $800k).
- **Contexto:** Ahora incluye Precio y OBI en cada alerta.

### 2. Senior Intelligence & Signal Fusion
- **Fusión de Confluencia:** El sistema ahora detecta cuando un `SPOOF` (retirada de muros) es seguido por un flip de OBI/CVD en menos de 20s, generando una alerta de `⚔️ FUSION`.
- **Integración de Capas:** `OpportunityTask` ahora consume datos de `AbsorptionDetector` (Toxicity, Icebergs) y `watchlist_levels.json`.

### 3. Infraestructura de Señales
- **SignalBus Extendido:** Se añadió el método `get_recent` para permitir que los daemons consulten el historial de señales reciente por tiempo y activo.
- **Telegram UI:** Formateo profesional con emojis de prioridad y separadores limpios.

## 📍 Estado Actual
- **Archivos Modificados:**
    - `daemons/Guardian_Daemon.py` (Lógica central de daemons y fusión).
    - `core/bus/__init__.py` (Historial de señales).
    - `alerts/gateway.py` (Visualización de alertas).
- **Pendientes:**
    - Calibración dinámica de umbrales para alts (Percentil 99).
    - Conectar el `ExecutionEngine` para auto-scalping basado en veredictos `SeniorIntelligence`.

## 🛑 Instrucciones para Reiniciar
Para volver a encender el sistema con la nueva lógica:
```bash
./manage.sh start
```
