# 🚨 Emergency Recovery & State Report: 4 de Mayo, 2026

## 📍 Estado Post-Crash (Laptop)
El sistema colapsó aproximadamente a las 23:24 mientras se lanzaba el `ml_dashboard.py`. Se han identificado bloqueos y errores críticos.

## 🔍 Hallazgos Técnicos

### 1. Bloqueos de Sistema (Stale Locks)
- **Action Server**: Está bloqueado por un mutex persistente.
  - Archivo: `/home/wek/.sema4ai/action-server/funding_action_server_7c12ff92/action_server.lock`
  - Error: `timed out waiting for mutex to be released`.
- **PID Files**: Existen archivos `.pid` huérfanos en `data/` que no corresponden a procesos activos.
  - `controller.pid`: 41534
  - `guardian.pid`: 41532
  - `server.pid`: 41536

### 2. Crash del Guardian Daemon
Se detectó una excepción en los logs justo antes del colapso:
- **Error**: `AttributeError: 'CurationBuffer' object has no attribute 'VPIN_THRESHOLD'`
- **Ubicación**: `alerts/gateway.py`, línea 325, en la función `_synthesize`.
- **Causa**: Intento de acceder a un atributo inexistente en `CurationBuffer`.

### 3. ML Dashboard
- El lanzamiento fue interrumpido. El dashboard depende de `logs/execution_features.jsonl` y de una conexión a Redis local.

## 🛠 Plan de Recuperación (Siguiente Ciclo)

### Paso 1: Limpieza de Residuos
Ejecutar lo siguiente para liberar el sistema:
```bash
./manage.sh stop
rm data/*.pid
rm /home/wek/.sema4ai/action-server/funding_action_server_7c12ff92/action_server.lock
```

### Paso 2: Fix del Bug en `alerts/gateway.py`
Es necesario corregir la referencia a `VPIN_THRESHOLD`. Probablemente deba ser un atributo de la clase `AlertGateway` o estar definido globalmente.

### Paso 3: Reinicio Controlado
1.  **Redis**: Asegurarse de que `redis-server` está corriendo.
2.  **Action Server**: `./manage.sh start` y verificar con `curl` (ver instrucciones en `SESSION_HANDOVER_4_MAYO.md`).
3.  **Guardian**: Reiniciar y monitorear `data/guardian_daemon.log`.
4.  **Dashboard**: Lanzar con `streamlit run ml_dashboard.py`.

## 📋 Pendientes Críticos
- [ ] Corregir `AttributeError` en `alerts/gateway.py`.
- [ ] Resolver Deadlocks en flujos compuestos (Action Server) descritos en el handover previo.
- [ ] Verificar consistencia de `zscore_elite_*.json` generados a las 23:21.

---
*Documentado por Gemini CLI Recovery Module.*
