---
description: System Health & Diagnostic Routine
---

// turbo-all
# System Health Routine

Checks the operational status of the Action Server, Data Engine, and Daemons.

## 1. Action Server Connectivity
Verify if the server is responsive and listing actions.

```bash
# List all active actions
curl -X GET http://localhost:8080/api/actions/funding-action-server/list -H "Content-Type: application/json" > server_actions.json
```

## 2. Data Engine Sanity Check
Fetch a ticker to verify exchange connectivity and API reachability.

```bash
# Fetch test ticker via tactical report (Target BTC)
curl -X POST http://localhost:8080/api/actions/funding-action-server/get-tactical-report/run -H "Content-Type: application/json" -d '{"assets": "BTC", "strategy": "scalp"}' > health_check.json
```

## 3. Daemon Log Inspection
Check the last few lines of the bot logs to detect errors or crashes.

```bash
tail -n 20 /home/wek/Escritorio/ccxtv2/bot_final.log
```
