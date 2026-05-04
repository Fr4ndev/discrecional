"""
ReactiveRouter — Mapea señales del Guardian a flows automáticos.
Filosofía: el Guardian detecta → el Router decide qué correr → sin intervención humana.
"""

import subprocess
import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("ccxtv2.reactive_router")

# ── Mapa de señal → flow ──────────────────────────────────────
# Regla PhD: el timeframe del trigger dicta el flow a ejecutar.
# HTF (Daily/Weekly/Monthly) → intraday audit completo
# 4H/ICT → turbo (microstructure)
# SFP → sfp confluence
# Whale/Scalp/Squeeze → scalp
# Toxicity spike (VPIN > 0.75) → omega completo

SIGNAL_FLOW_MAP = {
    # Señal (lowercase, coincide con sentinel.name.lower()) → flow
    "levelbreak":      "intraday",   # Key levels HTF → audit completo
    "strategicaudit":  "intraday",   # HTF Z-scores → intraday
    "ict_v16_4h":      "turbo",      # ICT 4H → microstructure turbo
    "ict":             "turbo",
    "sfp_v2":          "sfp",        # SFP → sfp confluence
    "sfp":             "sfp",
    "whalemonitor":    "scalp",      # Whale → scalp
    "squeezemonitor":  "scalp",      # Squeeze → scalp
    "ignitionbridge":  "turbo",      # Ignition → turbo
    "spoofdetector":   "scalp",
}

from core.Core_Intelligence_Hub import VPIN_THRESHOLD

# Flows que requieren VPIN >= umbral para ejecutarse
FLOW_VPIN_GATE = {
    "intraday": VPIN_THRESHOLD,
    "turbo":    VPIN_THRESHOLD,
    "sfp":      0.55,   # SFP puede ejecutarse con menos toxicidad
    "scalp":    0.50,
}

# Cooldown por flow (segundos) — evita loops de ejecución
FLOW_COOLDOWN = {
    "intraday": 300,    # máx 1 vez cada 5 min
    "turbo":    120,
    "sfp":      180,
    "scalp":    60,
    "omega":    600,    # omega es pesado, máx cada 10 min
}

FLOWS_SCRIPT = Path("scripts/ops/run_flows.sh")
OMEGA_SCRIPT  = Path("scripts/ignite_omega.sh")


@dataclass
class RouterTrigger:
    signal_type: str
    symbol: str
    vpin: float
    description: str
    timeframe: str = "unknown"


class ReactiveRouter:
    """
    Escucha triggers del Guardian y ejecuta el flow correspondiente.
    Se instancia UNA VEZ y se pasa al Guardian.
    """

    def __init__(self):
        self._last_run: dict = {}   # flow → timestamp última ejecución
        self._lock = asyncio.Lock()

    async def on_signal(self, trigger: RouterTrigger) -> Optional[str]:
        """
        Punto de entrada. Llamar desde BaseSentinelTask.alert() o dispatch_enriched_alert().
        Retorna el nombre del flow ejecutado, o None si bloqueado.
        """
        flow = self._resolve_flow(trigger)
        if not flow:
            return None

        async with self._lock:
            if not self._check_cooldown(flow):
                logger.debug(f"[Router] {flow} en cooldown, skip.")
                return None

            if not self._check_vpin_gate(flow, trigger.vpin):
                logger.info(
                    f"[Router] {flow} bloqueado: VPIN={trigger.vpin:.3f} "
                    f"< {FLOW_VPIN_GATE.get(flow, 0.62)}"
                )
                return None

            logger.info(
                f"[Router] 🎯 Trigger: {trigger.signal_type} → "
                f"Ejecutando flow: {flow} (VPIN={trigger.vpin:.3f})"
            )
            self._update_cooldown(flow)

        # Ejecutar fuera del lock para no bloquear otros triggers
        await self._run_flow(flow, trigger)
        return flow

    # ── Privados ──────────────────────────────────────────────

    def _resolve_flow(self, trigger: RouterTrigger) -> Optional[str]:
        key = trigger.signal_type.lower()
        # Match exacto primero, luego parcial
        if key in SIGNAL_FLOW_MAP:
            return SIGNAL_FLOW_MAP[key]
        for pattern, flow in SIGNAL_FLOW_MAP.items():
            if pattern in key:
                return flow
        return None

    def _check_cooldown(self, flow: str) -> bool:
        import time
        last = self._last_run.get(flow, 0)
        return (time.time() - last) > FLOW_COOLDOWN.get(flow, 120)

    def _update_cooldown(self, flow: str) -> None:
        import time
        self._last_run[flow] = time.time()

    def _check_vpin_gate(self, flow: str, vpin: float) -> bool:
        return vpin >= FLOW_VPIN_GATE.get(flow, 0.62)

    async def _run_flow(self, flow: str, trigger: RouterTrigger) -> None:
        try:
            if flow == "omega":
                cmd = ["bash", str(OMEGA_SCRIPT)]
            else:
                cmd = ["bash", str(FLOWS_SCRIPT), flow]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

            if proc.returncode == 0:
                logger.info(f"[Router] ✅ Flow '{flow}' completado para {trigger.symbol}")
            else:
                logger.error(
                    f"[Router] ❌ Flow '{flow}' error: {stderr.decode()[:300]}"
                )
        except asyncio.TimeoutError:
            logger.error(f"[Router] ⏱ Flow '{flow}' timeout 120s")
        except Exception as e:
            logger.error(f"[Router] Excepción en flow '{flow}': {e}")


# Singleton global — importar desde cualquier módulo
_router_instance: Optional[ReactiveRouter] = None

def get_router() -> ReactiveRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = ReactiveRouter()
    return _router_instance
