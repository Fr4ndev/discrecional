# README de Daemons

Documento tecnico de la migracion recomendada (Gemini) a arquitectura de 3 capas:

- `sensors/` (detectan y reportan)
- `core/bus.py` + `core/signals.py` (distribuyen eventos)
- `engine/synthesis_engine.py` (correlaciona y decide alerta final)

## Regla de oro aplicada

- Se conserva la logica core de deteccion de los daemons legacy.
- No se borran daemons existentes.
- Se cambia el "cableado" de salida hacia un bus de senales.

## Contrato de senal

Archivo: `core/signals.py`

`MarketSignal` define:

- `source`: nombre del sensor/daemon
- `symbol`: activo
- `signal_type`: tipo de evento (ej. `sfp_signal`, `liquidity_spoof`)
- `intensity`: valor entre 0.0 y 1.0
- `payload`: metadatos adicionales (OBI, precio, raw line, etc.)

## Bus asincrono

Archivo: `core/bus.py`

`SignalBus` implementa:

- cola asincrona (`asyncio.Queue`)
- `publish(signal)` para productores
- `subscribe(signal_type, handler)` y `subscribe_all(handler)` para consumidores
- loop interno de despacho no bloqueante

## Sensores

Archivos:

- `sensors/base.py`
- `sensors/legacy_daemon_sensors.py`
- `sensors/registry.py`

Se usa `BaseSensor` como clase base comun con:

- referencia al bus
- ciclo de vida (`run`, `stop`)
- helper `publish(...)`

Implementacion actual conservadora:

- Los 9 sensores consumen output de logs legacy y lo publican como `MarketSignal`.
- Esto evita romper los calculos de trading mientras migra el flujo.

## Motor de sintesis

Archivo: `engine/synthesis_engine.py`

Funcion:

- escucha todo el bus
- agrupa eventos por ventana temporal
- detecta confluencias entre sensores para emitir alerta de **Alta Conviccion**

Regla base:

- al menos 2 sensores distintos
- mismo simbolo
- dentro de 30 segundos (configurable)
- suma de intensidad sobre umbral

Solo el motor final envia Telegram (via `engine/notifiers.py`).

## Orquestador unificado

Archivo: `main.py`

Levanta todo en un solo proceso `asyncio` (opcion A recomendada):

1. inicia `SignalBus`
2. inicia `SynthesisEngine`
3. lanza los 9 sensores como tareas concurrentes

Ejecucion:

```bash
python3 -u main.py
```

## Siguiente fase recomendada (sin romper)

Fase 2: mover cada daemon para publicar en bus de forma nativa (`self.bus.publish(...)`) en vez de depender del tail de logs.

Plan seguro:

1. mantener daemon legacy intacto
2. extraer clase sensor nativa por daemon
3. activar por flag de config
4. comparar salida legacy vs bus antes de retirar salida directa
