#!/bin/bash
cd "$(dirname "$0")/../.."
echo "Calentando el buffer de OI (Necesario para el Trigger)..."
for i in {1..10}; do
  echo "Llamada $i..."
  curl -s -X POST http://127.0.0.1:8082/api/actions/funding-action-server/get-open-interest-snapshot/run \
    -H "Content-Type: application/json" \
    -d '{"assets":"BTC"}' | jq '.detail | to_entries[] | select(.key | contains("binance")) | .value.delta_pct'
  sleep 5
done
