#!/bin/bash
cd "$(dirname "$0")/../.."
set -e

# --- Configuration ---
REDIS_PORT=6379
ACTION_SERVER_PORT=8080
STREAMLIT_PORT=8501
PROJECT_DIR="/home/wek/Escritorio/ccxtv2"

echo "🚀 ATTUNING TO 'GOD MODE' — INITIATING ALPHA STACK..."

# 1. Health Check Cero: Redis
if ! redis-cli -p $REDIS_PORT ping > /dev/null 2>&1; then
    echo "❌ ERROR: Redis-server is OFFLINE on port $REDIS_PORT."
    echo "🚨 ACTION REQUIRED: Run 'sudo systemctl start redis' or 'redis-server &'"
    exit 1
fi
echo "🟢 [0/4] Redis: ONLINE"

# Cleanup function for CTRL+C
cleanup() {
    echo -e "\n\n🛑 SHUTTING DOWN ALPHA STACK..."
    kill $(jobs -p) 2>/dev/null || true
    echo "✅ All processes terminated. Standing down."
    exit
}
trap cleanup SIGINT SIGTERM

# 2. Capa de Datos: Action Server
echo "🕒 [1/4] Starting Action Server..."
action-server start --auto-reload --port $ACTION_SERVER_PORT --dir $PROJECT_DIR/funding_action_server > /dev/null 2>&1 &

# 3. Wait-For-It: Loop until responsive
echo -n "🕒 [2/4] Waiting for Action Server to stabilize..."
until curl -s "http://localhost:$ACTION_SERVER_PORT/api/actions/funding-action-server/list" > /dev/null; do
    echo -n "."
    sleep 1
done
echo -e "\n🟢 Action Server: LIVE"

# 4. Capa de Observabilidad: Streamlit
echo "🕒 [3/4] Launching ML Dashboard..."
streamlit run $PROJECT_DIR/ml_dashboard.py --server.port $STREAMLIT_PORT --server.headless true > /dev/null 2>&1 &
echo "🟢 Dashboard: READY @ http://localhost:$STREAMLIT_PORT"

# 5. Capa de Ejecución: Predatory Sniper
echo "🔥 [4/4] ACTIVATING PREDATORY SNIPER (Live Capture)..."
python3 $PROJECT_DIR/activate_predatory_sniper.py --telemetry-enabled --ml-capture
