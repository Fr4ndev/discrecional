# Mapeo de Senales - Fase Final

Este reporte resume los `signal_type` nativos emitidos por los 9 sensores refactorizados a `BaseSensor` + `SignalBus`.

## 1) `daemons/sfp_advanced_monitor.py`

- `sfp_confirmed`
  - **Cuándo emite:** cuando la auditoria SFP supera `SCORE_THRESHOLD` y cooldown.
  - **symbol:** `ticker.name` (ej. BTC, ETH).
  - **intensity:** `audit.score / audit.max_score`.
  - **payload clave:** `source_symbol`, `timeframe`, `entry`, `sweep_type`, `level`, `extreme_price`, `score`, `max_score`, `basis`, `obi`, `cvd_k`, `session`, `raw_alert`.

## 2) `daemons/opportunity_sentinel.py`

- `obi_flip_bull`
- `obi_flip_bear`
- `cvd_flip_bull`
- `cvd_flip_bear`
- `resistance_touch`
- `support_touch`
- `opportunity_alert` (fallback)
  - **Cuándo emite:** por cada alerta ya detectada por la logica original.
  - **symbol:** nombre de activo (`BTC`/`ETH`).
  - **intensity:** derivada del porcentaje de confianza del mensaje (`0.0..1.0`).
  - **payload clave:** `source_symbol`, `timeframe`, `price`, `obi`, `cvd_ratio`, `raw_alert`.

## 3) `daemons/level_break_alert.py`

- `level_breakout_down`
- `level_breakout_up`
- `level_rejection_bear`
- `level_rejection_bull`
  - **Cuándo emite:** en los mismos puntos donde antes enviaba Telegram (breakout/rejection confirmados).
  - **symbol:** nombre de activo (`BTC`/`ETH`).
  - **intensity:** `abs(obi)` normalizado a `0.0..1.0`.
  - **payload clave:** `source_symbol`, `timeframe`, `level`, `price`, `obi`, `raw_alert`.

## 4) `daemons/squeeze_watcher.py`

- `squeeze_high_conviction`
- `squeeze_warning`
  - **Cuándo emite:** score `3/3` (HC) o `2/3` (warning), con sus cooldowns originales.
  - **symbol:** `ETH`.
  - **intensity:** fija (`0.95` HC, `0.68` warning).
  - **payload clave:** `source_symbol`, `timeframe`, `price`, `funding_rate`, `obi`, `cvd_ratio`, `raw_alert`.

## 5) `daemons/whale_sentinel.py`

- `whale_buy`
- `whale_sell`
  - **Cuándo emite:** cuando detecta trade >= umbral de ballena por activo.
  - **symbol:** nombre de activo (`BTC`, `ETH`, etc.).
  - **intensity:** `1.0`.
  - **payload clave:** `source_symbol`, `timeframe`, `side`, `amount`, `price`, `usd_value`.

## 6) `daemons/volume_daemon.py`

- `volume_bullish`
- `volume_bearish`
  - **Cuándo emite:** desequilibrio de volumen (buy/sell > 1.5 o inverso).
  - **symbol:** nombre de activo.
  - **intensity:** derivada de `ratio` (con piso 0.4).
  - **payload clave:** `source_symbol`, `timeframe`, `buy_vol`, `sell_vol`, `ratio`.

## 7) `daemons/spoof_daemon.py`

- `spoofing_detected`
  - **Cuándo emite:** delta OBI > `SNAP_THRESHOLD`.
  - **symbol:** nombre de activo.
  - **intensity:** `min(1.0, obi_delta)`.
  - **payload clave:** `source_symbol`, `timeframe`, `obi_prev`, `obi_now`, `obi_delta`.

## 8) `daemons/ignition_daemon.py`

- `coordinated_ignition_up`
- `coordinated_ignition_down`
- `coordinated_ignition_eth_lead`
- `coordinated_ignition_btc_lead`
  - **Cuándo emite:** estado no-neutral de coordinación BTC/ETH.
  - **symbol:** `BTC` (símbolo ancla del evento global).
  - **intensity:** `max(abs(btc_obi), abs(eth_obi))`.
  - **payload clave:** `timeframe`, `btc_symbol`, `eth_symbol`, `btc_obi`, `eth_obi`, `btc_price`, `eth_price`, `status`.

## 9) `daemons/scalp_daemon.py`

- `scalp_long`
- `scalp_short`
- `scalp_avoid_long`
  - **Cuándo emite:** cambio de estado de oportunidad scalp por activo.
  - **symbol:** activo analizado.
  - **intensity:** 0.75 (long/short), 0.6 (avoid).
  - **payload clave:** `timeframe`, `alert_type`, `obi_20`, `basis_pct`, `raw_alert`.

## Reglas maestras del motor (`engine/synthesis_engine.py`)

- `combo_institucional`: `sfp_confirmed` + `level_rejection_*`
- `the_institutional_whale`: combo institucional + `whale_buy/sell` alineado
- `combo_squeeze`: `squeeze_high_conviction` + `obi_flip_*`/`cvd_flip_*`
- `combo_breakout`: `level_breakout_*` + `cvd_flip_*` alineado
- `global_ignition`: breakout o squeeze + `coordinated_ignition_*`
- `interes_incrementado`: suma ponderada de intensidades supera umbral

## Matriz de pesos

- SFP y Rejections: `1.0`
- Squeeze HC: `0.8`
- Breakouts: `0.7`
- Flips OBI/CVD: `0.4`
- Default no mapeados: `0.5`

## Dry Run implementado

Cada archivo incluye `--dry-run` bajo `if __name__ == "__main__"` que:

1. crea un `SignalBus`,
2. registra un subscriber de captura,
3. publica una senal simulada,
4. verifica recepcion (si falla, levanta excepcion).

Comandos:

```bash
python3 daemons/opportunity_sentinel.py --dry-run
python3 daemons/level_break_alert.py --dry-run
python3 daemons/squeeze_watcher.py --dry-run
python3 daemons/sfp_advanced_monitor.py --dry-run
python3 daemons/whale_sentinel.py --dry-run
python3 daemons/volume_daemon.py --dry-run
python3 daemons/spoof_daemon.py --dry-run
python3 daemons/ignition_daemon.py --dry-run
python3 daemons/scalp_daemon.py --dry-run
```
