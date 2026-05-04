#!/bin/bash
ASSETS="BTC,ETH"
BTC_SYM="BTC/USDT:USDT"
ETH_SYM="ETH/USDT:USDT"
BASE_URL="http://localhost:8080/api/actions/funding-action-server"

# FLOW-INTRADAY
curl -s -X POST "$BASE_URL/get-basis/run" -H "Content-Type: application/json" -d '{"symbol_spot": "BTC/USDT", "symbol_perp": "BTC/USDT:USDT"}' > intraday_basis_btc.json &
curl -s -X POST "$BASE_URL/get-basis/run" -H "Content-Type: application/json" -d '{"symbol_spot": "ETH/USDT", "symbol_perp": "ETH/USDT:USDT"}' > intraday_basis_eth.json &
curl -s -X POST "$BASE_URL/get-tactical-report/run" -H "Content-Type: application/json" -d "{\"assets\": \"$ASSETS\", \"strategy\": \"scalp\"}" > intraday_tactical_scalp.json &
curl -s -X POST "$BASE_URL/get-tactical-report/run" -H "Content-Type: application/json" -d "{\"assets\": \"$ASSETS\", \"strategy\": \"swing\"}" > intraday_tactical_swing.json &
curl -s -X POST "$BASE_URL/get-ultra-deep-confluence/run" -H "Content-Type: application/json" -d "{\"assets\": \"$ASSETS\", \"depth\": 100}" > intraday_udc.json &

# FLOW-SWING
curl -s -X POST "$BASE_URL/get-full-market-snapshot/run" -H "Content-Type: application/json" -d "{\"assets\": \"$ASSETS\", \"ob_depth\": 50}" > swing_snapshot.json &
curl -s -X POST "$BASE_URL/get-basis/run" -H "Content-Type: application/json" -d '{"symbol_spot": "BTC/USDT", "symbol_perp": "BTC/USDT:USDT"}' > swing_basis_btc.json &
curl -s -X POST "$BASE_URL/get-basis/run" -H "Content-Type: application/json" -d '{"symbol_spot": "ETH/USDT", "symbol_perp": "ETH/USDT:USDT"}' > swing_basis_eth.json &

# ALPHA IGNITION
curl -s -X POST "$BASE_URL/get-full-market-snapshot/run" -H "Content-Type: application/json" -d '{"assets": "BTC,ETH,SOL,HYPE"}' > alpha_snapshot.json &
curl -s -X POST "$BASE_URL/microstructure-audit/run" -H "Content-Type: application/json" -d '{"symbol": "BTC/USDT:USDT"}' > btc_ignition_audit.json &
curl -s -X POST "$BASE_URL/microstructure-audit/run" -H "Content-Type: application/json" -d '{"symbol": "ETH/USDT:USDT"}' > eth_ignition_audit.json &

wait
echo "All done"
