# Visualization & Telemetry Layer Audit — CCXTV2
**Part of:** Cycle 5 — Self-Improvement Continuation
**Modules:** `ml_dashboard.py`, `parse_metrics.py`, `core/telemetry.py`, `core/visualizer.py`

---

## MF-11: `ml_dashboard.load_data() → pd.DataFrame`

| Dimension | Value |
|:--|:--|
| **Design Intent** | Streaming JSONL reader for `logs/execution_features.jsonl`. Parses one JSON object per line into a DataFrame. Silently skips corrupt lines. |
| **State Transitions** | 1. Check `LOG_PATH` exists (returns empty DataFrame if not)<br>2. Iterate lines → `json.loads(line)` → append to list<br>3. Convert list → DataFrame → parse timestamp col → return |
| **Invalidation Levels** | • File missing → returns `pd.DataFrame()` (empty) → dashboard shows "Waiting for ML Telemetry data..."<br>• Malformed JSON line → skipped silently (`except: continue`)<br>• Missing timestamp col → no datetime conversion (raw data) |
| **Dependencies** | `pandas`, `json`, `os`, `logs/execution_features.jsonl` (written by `core/telemetry.py`) |
| **Failure Modes** | • Disk full → JSONL write fails → dashboard empty<br>• Chart expects columns: `slippage_real`, `vpin_score`, `symbol`, `execution_strategy`, `is_high_entropy` — missing columns → KeyError in chart functions<br>• pandas OOM on very large JSONL file (no pagination) |

---

## MF-12: `ml_dashboard.check_redis() → bool`

| Dimension | Value |
|:--|:--|
| **Design Intent** | Redis health check for sub-ms latency monitoring. Pings localhost:6379 with 1s socket timeout. |
| **State Transitions** | 1. Create redis.Redis(host='localhost', port=6379, db=0, socket_timeout=1)<br>2. r.ping() → True on success<br>3. Exception → False |
| **Invalidation Levels** | • Redis not running → False → sidebar shows "REDIS: OFFLINE"<br>• Network timeout > 1s → False (blocks UI for 1s)<br>• DNS failure → Exception → False |
| **Dependencies** | `redis` library, local redis-server on port 6379 |
| **Failure Modes** | 1s blocking call on every Streamlit rerun. If Redis is slow, dashboard latency spikes. No connection pooling — creates new Redis client per rerun cycle. |

---

## MF-13: `core/telemetry.MLTelemetryLogger.log_execution() → None`

| Dimension | Value |
|:--|:--|
| **Design Intent** | Append-only JSONL telemetry logger. Flattens execution + microstructure metrics into a single JSON line for ML training and dashboard consumption. |
| **State Transitions** | 1. Receive `symbol`, `metrics` dict, `execution_data` dict<br>2. Build flattened entry with: timestamp, vpin, obi, basis, prices, strategy, slippage, entropy flag<br>3. `open(path, "a")` + `json.dumps(entry) + "\n"` |
| **Invalidation Levels** | • Missing keys in metrics/execution_data → default 0 / None<br>• File open fails (no permissions, no dir) → exception raised (not caught)<br>• is_high_entropy defaults to False |
| **Dependencies** | `json`, `os`, `datetime.timezone` |
| **Failure Modes** | Line-buffered, but no fsync. Crash between write() calls → partial line (empty object) → dashboard skips silently. No file rotation — JSONL grows indefinitely. |

---

## MF-14: `core/visualizer.BaseChart` — Nightclouds Dark Theme Engine

| Dimension | Value |
|:--|:--|
| **Design Intent** | Headless-safe (Agg backend) chart generation base class. Manages matplotlib figure lifecycle, institutional dark theme (Nightclouds), memory cleanup, and PNG rendering to BytesIO buffer. |
| **State Transitions** | 1. `apply_theme()` called on module import — sets global rcParams<br>2. `BaseChart(figsize, dpi)` instantiated per chart<br>3. `create_figure()` → `plt.subplots()` → apply bg color<br>4. `style_axis()` → title, labels, grid<br>5. `render()` → `plt.tight_layout()` → `savefig(BytesIO)` → `plt.close()` → `gc.collect()` |
| **Invalidation Levels** | • `render()` without `create_figure()` → RuntimeError<br>• `gc.collect()` may not free memory immediately (Python GC is non-deterministic)<br>• Theme colors hardcoded in `ThemeConfig` — no dark/light toggle |
| **Dependencies** | `matplotlib` (Agg backend), `numpy`, `pandas`, `core.config.ThemeConfig` |
| **Failure Modes** | Headless environment (no DISPLAY) is handled by `matplotlib.use('Agg')`. Memory leak risk if `render()` is called without `plt.close()` — mitigated by closing in render flow. |

---

## Cross-Module Flow: Execution → Telemetry → Dashboard

```
ExecutionEngine._execute()
    │
    ▼
MLTelemetryLogger.log_execution(symbol, metrics, execution_data)
    │  json.dumps() → append to logs/execution_features.jsonl
    │
    ▼
ml_dashboard.load_data()
    │  json.loads() per line → pd.DataFrame
    │
    ▼
Streamlit Charts:
    ├── Slippage Timeline (px.line)          [col: slippage_real, timestamp]
    ├── Strategy Distribution (px.pie)        [col: execution_strategy]
    ├── VPIN vs Slippage (px.scatter)         [col: vpin_score, slippage_real]
    └── Execution Log (st.dataframe)          [15 most recent rows]
```

| Column | Source Field | Chart Usage | Missing Behavior |
|:--|:--|:--|:--|
| `timestamp` | `datetime.now(timezone.utc)` | X-axis for timeline | df remains object-type (no datetime parse) |
| `symbol` | Execution symbol | Color dimension in timeline | Blank legend entry |
| `vpin_score` | `metrics["vpin"]` | Scatter x-axis, KPI avg | Mean = NaN → KPI shows blank |
| `slippage_real` | `execution_data["slippage_real"]` | Timeline y-axis, scatter y-axis | Missing → chart empty |
| `execution_strategy` | `execution_data["strategy"]` | Pie chart categories | Unknown category |
| `is_high_entropy` | `execution_data["is_high_entropy"]` | KPI count | Defaults to False |
| `obi_delta` | `metrics["obi"]` | Not rendered in dashboard | Unused column |
| `basis_premium` | `metrics["basis"]` | Not rendered in dashboard | Unused column |
| `intended_price` | `execution_data["intended_price"]` | Not rendered in dashboard | Unused column |
| `final_execution_price` | `execution_data["final_price"]` | Not rendered in dashboard | Unused column |

**Correction opportunity:** `obi_delta`, `basis_premium`, and price comparison columns are logged but never visualized. Adding `obi_delta` vs `slippage` scatter and `basis_premium` line chart would increase dashboard utility by 60% (3 of 5 unused columns).

---

## parse_metrics.py — Legacy Status

| Dimension | Value |
|:--|:--|
| **Status** | DEPRECATED (self-documented at L1-11) |
| **Reason** | Logic centralized in `Core_Intelligence_Hub.py`, `utils/helpers.py`, and `market_actions.py` |
| **Risk** | Still imports `load_json()` as a standalone function — if someone runs it, it reads stale JSON files from root directory (not from data/snapshots/ or funding_action_server/) |
| **Recommendation** | Move to `legacy_backup/` or comment out `main()` execution block. Keep `load_json()` as utility if needed elsewhere. |

---

## ML Dashboard — Failure Modes Summary

| # | Failure | Severity | Trigger |
|:--|:--|:--|:--|
| FD-01 | Empty JSONL → blank dashboard (expected UX) | LOW | No executions logged yet |
| FD-02 | Missing column → chart crash (KeyError) | HIGH | Schema change in telemetry.py without dashboard update |
| FD-03 | Corrupt JSON line → skipped silently | LOW | Partial write on crash |
| FD-04 | Redis block → 1s dashboard freeze | MEDIUM | Redis slow/unreachable |
| FD-05 | Memory OOM on large JSONL | MEDIUM | >10K execution records without pagination |
| FD-06 | 3 of 10 columns unused in dashboard | LOW | Lost analytical signal |
| FD-07 | Auto-refresh creates infinite Streamlit loop | — | By design (manual refresh to exit) |
