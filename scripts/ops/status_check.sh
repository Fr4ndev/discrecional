#!/bin/bash
cd "$(dirname "$0")/../.."
# status_check.sh — System Health Diagnostics
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo "🏥 CCXTV2 System Health Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Redis
if redis-cli ping > /dev/null 2>&1; then
    echo "🟢 Redis: ONLINE"
else
    echo "🔴 Redis: OFFLINE"
fi

# 2. Action Server
if curl -s http://localhost:8080/api/health > /dev/null 2>&1; then
    echo "🟢 Action Server: ONLINE (Port 8080)"
elif curl -s http://localhost:8080/api/actions/funding-action-server/get-full-market-snapshot/run -d '{"assets": "BTC"}' > /dev/null 2>&1; then
    echo "🟢 Action Server: ONLINE (Responding)"
else
    echo "🔴 Action Server: OFFLINE or UNREACHABLE"
fi

# 3. Core Daemons
DAEMONS=("Guardian_Daemon" "sfp_advanced_monitor" "level_break_alert")
for d in "${DAEMONS[@]}"; do
    if ps aux | grep "$d" | grep -v grep > /dev/null; then
        echo "🟢 Daemon [$d]: RUNNING"
    else
        echo "🔴 Daemon [$d]: NOT FOUND"
    fi
done

# 4. Snapshot Freshness
if [ -d "data/snapshots" ]; then
    LATEST_JSON=$(ls -t data/snapshots/*.json 2>/dev/null | head -n 1)
    if [ ! -z "$LATEST_JSON" ]; then
        echo "📅 Latest Snapshot: $LATEST_JSON ($(stat -c %y "$LATEST_JSON" | cut -d'.' -f1))"
    fi
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
