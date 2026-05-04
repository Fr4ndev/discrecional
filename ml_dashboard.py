import streamlit as st
import pandas as pd
import json
import os
import plotly.express as px
import plotly.graph_objects as go
import time
import redis

# --- Page Config ---
st.set_page_config(page_title="Institutional Alpha | ML Telemetry", layout="wide", initial_sidebar_state="expanded")
st.title("🛡️ Institutional ML Dashboard — Execution Alpha")

LOG_PATH = "/home/wek/Escritorio/ccxtv2/logs/execution_features.jsonl"

def load_data():
    if not os.path.exists(LOG_PATH):
        return pd.DataFrame()
    data = []
    with open(LOG_PATH, 'r') as f:
        for line in f:
            try:
                data.append(json.loads(line))
            except:
                continue
    df = pd.DataFrame(data)
    if not df.empty and 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

def check_redis():
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, socket_timeout=1)
        return r.ping()
    except:
        return False

# --- Sidebar ---
st.sidebar.markdown("### ⚙️ System Health")
redis_ok = check_redis()
if redis_ok:
    st.sidebar.success("🟢 Redis: ONLINE (Sub-ms latency)")
else:
    st.sidebar.error("🔴 Redis: OFFLINE (Check systemctl!)")

st.sidebar.markdown("### 🔄 Control Panel")
auto_refresh = st.sidebar.checkbox("Live Auto-Refresh (2s)", value=True)
if st.sidebar.button("Manual Refresh"):
    st.rerun()

# --- Main Dashboard ---
df = load_data()

if not df.empty:
    # --- Top KPIs ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Executions", len(df))
    with col2:
        hi_entropy = df[df['is_high_entropy'] == True].shape[0]
        st.metric("High Entropy (Anomalies)", hi_entropy, delta_color="inverse")
    with col3:
        avg_slip = df['slippage_real'].mean() * 100
        st.metric("Avg Slippage", f"{avg_slip:.4f}%")
    with col4:
        avg_tox = df['vpin_score'].mean()
        st.metric("Avg Toxicity (VPIN)", f"{avg_tox:.2f}")

    st.divider()

    # --- Charts ---
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.subheader("⏱️ Slippage Timeline (Alpha Decay)")
        fig_time = px.line(df, x="timestamp", y="slippage_real", color="symbol", markers=True,
                           title="Real Slippage over Execution Time")
        fig_time.add_hline(y=0.0015, line_dash="dash", line_color="red", annotation_text="Slip-Guard Threshold (0.15%)")
        st.plotly_chart(fig_time, use_container_width=True)

    with c2:
        st.subheader("🧩 Strategy Distribution")
        fig_pie = px.pie(df, names="execution_strategy", hole=0.4, title="Market vs TWAP")
        st.plotly_chart(fig_pie, use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("☠️ VPIN vs Slippage")
        fig_scatter = px.scatter(df, x="vpin_score", y="slippage_real", color="execution_strategy",
                                 size_max=15, title="Toxicity Impact on Price")
        st.plotly_chart(fig_scatter, use_container_width=True)
        
    with c4:
        st.subheader("📊 Execution Log (JSONL Vector)")
        st.dataframe(df.sort_values(by="timestamp", ascending=False).head(15), use_container_width=True)

else:
    st.info("Waiting for ML Telemetry data... Run the Predatory Sniper to populate the matrix.")

# --- Auto-refresh Logic ---
if auto_refresh:
    time.sleep(2)
    st.rerun()
