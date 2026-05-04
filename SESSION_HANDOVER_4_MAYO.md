# 🤝 Session Handover: 4 de Mayo, 2026 - PhD Architectural Cohesion (Cycle 4)

## 📍 Estado Actual
El Ciclo 4 se centró en la **unificación de flujos compuestos** dentro del Action Server para reducir la dependencia de scripts bash externos. Se logró la integración de `run_scalp_workflow` y `run_intraday_workflow`, pero se identificaron conflictos de concurrencia críticos.

## ⚠️ Alerta: "La que he liado" (Diagnóstico Técnico)
Al intentar llamar a acciones desde otras acciones (ej: `run_scalp_workflow` llamando a `get_toxicity_index`), entramos en un **Deadlock de Event Loop**.
1. Cada acción decorada con `@action` usa un helper `_run_async` que crea un `new_event_loop()`.
2. Al anidarlos, el loop hijo intenta acceder a recursos compartidos (como el semáforo de `IntelligenceHub`) que pueden estar bloqueados por el loop padre o en un estado inconsistente.
3. **Resultado**: Timeouts infinitos en los endpoints compuestos.

## 🛠 Cambios Realizados
- **`audit_actions.py`**: Implementación de workflows compuestos (`run_scalp`, `run_intraday`, `detect_sfp`). Se corrigieron errores de linting (docstrings).
- **`market_actions.py`**: Se añadió el helper `_run_async` y se comenzó a exponer versiones `_internal` asíncronas para evitar loops anidados (pendiente completar).
- **`manage.sh`**: Verificación de estado operativa, aunque el archivo `data/server.pid` a veces se pierde si el servidor falla al arrancar.

## 🧪 Instrucciones de Prueba (Testing Suite)

### 1. Verificación de Salud Básica
```bash
# Comprobar que los demonios y el score básico funcionan
curl -s -X POST http://localhost:8080/api/actions/funding-action-server/get-system-health/run \
     -H "Content-Type: application/json" -d '{}' | jq .
```

### 2. Prueba de Microestructura (Atómica)
```bash
# Esta acción es estable porque no es compuesta
curl -s -X POST http://localhost:8080/api/actions/funding-action-server/microstructure-audit/run \
     -H "Content-Type: application/json" -d '{"symbol": "BTC/USDT:USDT"}' | jq .
```

### 3. Prueba de Workflows (¡Peligro de Timeout!)
```bash
# Si esto falla con timeout, confirmar el deadlock en logs/server_new.log
curl -m 10 -s -X POST http://localhost:8080/api/actions/funding-action-server/run-scalp-workflow/run \
     -H "Content-Type: application/json" -d '{"assets": "BTC"}' | jq .
```

## 📋 Pendiente para el Ciclo 5
1.  **Refactor Final de Loops**: Terminar de extraer la lógica de `market_actions.py` a funciones `async def ..._internal`.
2.  **Eliminar `_run_async` anidados**: Modificar los workflows en `audit_actions.py` para que hagan `await ..._internal` en lugar de llamar a la función decorada con `@action`.
3.  **Audit de `ignite_all_flows.sh`**: Una vez estables los endpoints, crear la versión V2 que use `curl` a los nuevos Composite Actions.

## 🆘 Recovery Manual
Si el Action Server se queda "colgado" por los deadlocks:
```bash
./manage.sh stop
# Matar procesos huérfanos si es necesario
ps aux | grep action-server | awk '{print $2}' | xargs kill -9
./manage.sh start
# Regenerar PID si manage.sh no lo detecta
pgrep -f "action-server start" > data/server.pid
```

---
*Documentado por Gemini CLI PhD Cohesion Module.*
