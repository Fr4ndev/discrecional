#!/bin/bash

# CCXTV2 Master Manager — Human-Friendly Control
# ═════════════════════════════════════════════

ROOT_DIR="/home/wek/Escritorio/ccxtv2"
DATA_DIR="$ROOT_DIR/data"
PID_GUARDIAN="$DATA_DIR/guardian.pid"
PID_CONTROLLER="$DATA_DIR/controller.pid"
KILL_SWITCH="$DATA_DIR/STOP_ALL.lock"
LOG_GUARDIAN="$DATA_DIR/guardian_daemon.log"
LOG_CONTROLLER="$ROOT_DIR/controller.log"
LOG_SERVER="$ROOT_DIR/funding_action_server/server_new.log"
PID_SERVER="$DATA_DIR/server.pid"

mkdir -p "$DATA_DIR"

show_status() {
    echo "--- CCXTV2 Status ---"
    if [ -f "$PID_GUARDIAN" ] && kill -0 $(cat "$PID_GUARDIAN") 2>/dev/null; then
        echo "[✅] Guardian: RUNNING (PID $(cat $PID_GUARDIAN))"
    else
        echo "[❌] Guardian: STOPPED"
        rm -f "$PID_GUARDIAN"
    fi

    if [ -f "$PID_CONTROLLER" ] && kill -0 $(cat "$PID_CONTROLLER") 2>/dev/null; then
        echo "[✅] Controller: RUNNING (PID $(cat $PID_CONTROLLER))"
    else
        echo "[❌] Controller: STOPPED"
        rm -f "$PID_CONTROLLER"
    fi

    if [ -f "$PID_SERVER" ] && kill -0 $(cat "$PID_SERVER") 2>/dev/null; then
        echo "[✅] Action-Server: RUNNING (PID $(cat $PID_SERVER))"
    else
        echo "[❌] Action-Server: STOPPED"
        rm -f "$PID_SERVER"
    fi
    
    if [ -f "$KILL_SWITCH" ]; then
        echo "[⚠️] KILL SWITCH IS ACTIVE: Systems will not start."
    fi
}

start_system() {
    rm -f "$KILL_SWITCH"
    echo "🚀 Starting CCXTV2 Ecosystem..."
    
    # 1. Start Guardian
    if [ -f "$PID_GUARDIAN" ] && kill -0 $(cat "$PID_GUARDIAN") 2>/dev/null; then
        echo "(!) Guardian already running."
    else
        nohup python3 -u "$ROOT_DIR/daemons/Guardian_Daemon.py" >> "$LOG_GUARDIAN" 2>&1 &
        echo $! > "$PID_GUARDIAN"
        echo "Guardian started."
    fi

    # 2. Start Controller
    if [ -f "$PID_CONTROLLER" ] && kill -0 $(cat "$PID_CONTROLLER") 2>/dev/null; then
        echo "(!) Controller already running."
    else
        nohup python3 -u "$ROOT_DIR/controller.py" >> "$LOG_CONTROLLER" 2>&1 &
        echo $! > "$PID_CONTROLLER"
        echo "Controller started."
    fi
    
    # 3. Start Action Server (Local Mode, No Auth)
    if [ -f "$PID_SERVER" ] && kill -0 $(cat "$PID_SERVER") 2>/dev/null; then
        echo "(!) Action-Server already running."
    else
        echo "📡 Starting Action-Server (Local Mode)..."
        cd "$ROOT_DIR/funding_action_server" && \
        nohup action-server start --port 8080 --dir . >> "$LOG_SERVER" 2>&1 &
        echo $! > "$PID_SERVER"
        echo "Action-Server started on port 8080."
    fi
    echo "✨ All systems online."
}

stop_system() {
    echo "🛑 Stopping everything..."
    touch "$KILL_SWITCH"
    
    # Kill PIDs
    [ -f "$PID_GUARDIAN" ] && kill $(cat "$PID_GUARDIAN") 2>/dev/null
    [ -f "$PID_CONTROLLER" ] && kill $(cat "$PID_CONTROLLER") 2>/dev/null
    [ -f "$PID_SERVER" ] && kill $(cat "$PID_SERVER") 2>/dev/null
    
    # Force cleanup of any lingering processes
    sleep 2
    pkill -9 -f Guardian_Daemon.py
    pkill -9 -f controller.py
    pkill -9 -f action-server
    
    rm -f "$PID_GUARDIAN" "$PID_CONTROLLER" "$PID_SERVER"
    echo "✅ Systems stopped and cleaned."
}

case "$1" in
    start)
        start_system
        ;;
    stop)
        stop_system
        ;;
    status)
        show_status
        ;;
    audit)
        echo "🧐 Initiating Senior Institutional Audit..."
        python3 "$ROOT_DIR/senior_audit_orchestrator.py"
        ;;
    logs)
        tail -f "$LOG_CONTROLLER"
        ;;
    clean-lock)
        rm -f "$KILL_SWITCH"
        echo "Lock removed."
        ;;
    *)
        echo "Usage: $0 {start|stop|status|logs|clean-lock}"
        exit 1
esac
