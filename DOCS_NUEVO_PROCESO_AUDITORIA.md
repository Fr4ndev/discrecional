# 📖 Guía de Auditoría Unificada (Senior Desk CCXTV2)

Este documento describe el nuevo proceso consolidado para realizar una auditoría institucional completa en un solo paso, optimizando la captura de datos y la generación de reportes.

---

## 🚀 1. Requisitos Previos

El **Action Server** debe estar corriendo en el puerto 8080. 
Para iniciarlo (si no está activo):
```bash
cd funding_action_server
action-server start
```

---

## 🛠️ 2. Ejecución Consolidada

Se ha estandarizado el uso de `scripts/ops/run_flows.sh` para ejecuciones modulares y `funding_action_server/run_comprehensive_flows.sh` para auditorías totales.

### Comandos de una sola línea:

#### A. Auditoría Total (Scalp + Intraday + Swing + Alpha)
Este comando corre todos los flujos concurrentemente y guarda los resultados en `funding_action_server/comprehensive_results/`.
```bash
bash funding_action_server/run_comprehensive_flows.sh
```

#### B. Auditoría de Confluencia SFP & Turbo (Senior Analyst)
Para obtener el veredicto del "Senior Analyst" (PhD Level):
```bash
bash scripts/ops/run_flows.sh turbo
bash scripts/ops/run_flows.sh sfp
```

---

## 📊 3. Flujo de Trabajo para el Senior Analyst

Para realizar un análisis completo y documentado:

1.  **Ejecutar el script de captura:**
    ```bash
    # Captura masiva de microestructura y basis
    bash funding_action_server/run_comprehensive_flows.sh
    ```
2.  **Ejecutar auditorías de confluencia:**
    ```bash
    # Detectar reversiones SFP y Veredicto Turbo
    bash scripts/ops/run_flows.sh turbo
    bash scripts/ops/run_flows.sh sfp
    ```
3.  **Generar Reporte:** 
    Los datos se consolidan en `data/snapshots/` y `funding_action_server/comprehensive_results/`.

---

## 🔧 4. Correcciones Realizadas (Audit Log)

### Error en `ele_transition_routine` (SOLUCIONADO)
- **Problema:** El motor `IntelligenceHub` no tenía el método público `fetch_ticker`, lo que causaba que `eth-ele-audit` fallara.
- **Solución:** 
    - Se añadió el método `get_ticker` y el alias `fetch_ticker` en `core/Core_Intelligence_Hub.py`.
    - Se corrigió la falta de `logging` en `funding_action_server/actions/audit_actions.py`.
- **Verificación:** `eth-ele-audit` ahora devuelve correctamente niveles SFP y potencial de transición.

---

## 📂 5. Ubicación de Reportes
Todos los reportes generados deben moverse a:
`reports_history/REPORTE_AUDITORIA_YYYYMMDD_HHMM.md`

---
*Senior Desk Intelligence Framework v2.1*
