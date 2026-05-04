#!/bin/bash
# start_ccxtv2.sh — Centralized PhD Intelligence Hub Startup
# ════════════════━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 1. Clear kill switch if it exists
rm -f data/STOP_ALL.lock

echo "🚀 Starting CCXTV2 PhD Intelligence Hub..."

# Function to start a process in a named tmux session
start_session() {
    local session_name=$1
    local command=$2
    if tmux has-session -t "$session_name" 2>/dev/null; then
        echo "⚠️ Session $session_name already exists. Killing it..."
        tmux kill-session -t "$session_name"
    fi
    tmux new-session -d -s "$session_name" "$command"
    echo "✅ Session [$session_name] started: $command"
}

# Start components in order
start_session "core"       "python3 core/Core_Intelligence_Hub.py"
sleep 2
start_session "gateway"    "python3 alerts/gateway.py"
sleep 1
start_session "guardian"   "python3 daemons/Guardian_Daemon.py"
sleep 1
start_session "controller" "python3 controller.py"

echo ""
echo "🔥 CCXTV2 PhD Hub is now patrolling."
echo "Inspect sessions with: tmux ls"
echo "View logs with: tmux attach -t guardian (Ctrl+B, D to detach)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
