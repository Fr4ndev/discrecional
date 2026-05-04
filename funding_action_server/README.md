# Funding Fees Market State Action Package

This package provides tools for monitoring multi-DEX funding rates and triggering market analysis.

## Actions

- `get_funding_rates_table`: Returns current funding rates for tracked assets.
- `detect_funding_anomalies`: Detects spikes in funding rates vs historical data.
- `run_full_market_analysis`: Triggers Z-Score, SpotDiff, and Heatmap analysis for a symbol.
- `get_funding_zscore_history`: Returns rolling z-score history for a specific pair.

## Setup & Run (Manual)

1. **Clean environment** (if previously broken):
   ```bash
   rm -rf ~/.sema4ai/action-server/funding_fees_market_state_*
   ```

2. **Update package**:
   ```bash
   action-server package update
   ```

3. **Start server**:
   ```bash
   action-server start --auto-reload --expose --port 8082 --dir .
   ```

## Requirements
- Python 3.11+
- `sema4ai-actions`
- `ccxt`, `pandas`, `numpy`, `beautifulsoup4`, `lxml`, `requests`
