import asyncio
import logging
import os
import traceback
from typing import Optional

from core.Core_Intelligence_Hub import IntelligenceHub
from alerts.gateway import SentinelGateway, AlertMessage

class BaseSentinelTask:
    """
    Mixin base for all sentinel tasks.
    Each task runs as an asyncio coroutine and shares the hub + gateway.
    """

    name: str = "BaseSentinel"
    poll_interval: float = 30.0     # seconds between cycles
    enabled_env_var: str = ""       # e.g. "DISABLE_SQUEEZE"

    def __init__(self, hub: IntelligenceHub, gateway: SentinelGateway):
        self.hub = hub
        self.gateway = gateway
        self._running = True
        self._cycles = 0
        self._errors = 0
        self.log = logging.getLogger(self.name)

    @property
    def is_enabled(self) -> bool:
        if self.enabled_env_var:
            return os.getenv(self.enabled_env_var, "0") != "1"
        return True

    async def run(self) -> None:
        """Supervised run loop. Override _cycle() in subclasses."""
        if not self.is_enabled:
            self.log.info(f"{self.name} DISABLED by env var.")
            return

        self.log.info(f"🚀 {self.name} STARTED (poll={self.poll_interval}s)")
        while self._running:
            self._cycles += 1
            try:
                await self._cycle()
                self._errors = 0
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._errors += 1
                self.log.error(f"[{self.name}] Cycle #{self._cycles} error #{self._errors}: {e}\n"
                               f"{traceback.format_exc()}")
                if self._errors >= 10:
                    self.log.critical(f"[{self.name}] Circuit breaker: 10 consecutive errors.")
                    await asyncio.sleep(120)
                    self._errors = 0
            await asyncio.sleep(self.poll_interval)

        self.log.info(f"🛑 {self.name} STOPPED.")

    async def _cycle(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        self._running = False

    async def alert(self, text: str, priority: int = 2,
                    dedup_key: str = "", symbol: str = "GLOBAL") -> None:
        # 1. Comportamiento existente (no tocar)
        await self.gateway.dispatch(AlertMessage(
            source=self.name, priority=priority,
            text=text, dedup_key=dedup_key,
        ))

        # 2. BLOQUE NUEVO — Enriquecimiento y Curación
        try:
            from alerts.gateway import AlertSignal
            from core.hub_reader import get_live_metrics
            
            # Read real metrics from Hub (Async)
            m = await get_live_metrics(symbol=symbol)
            
            signal = AlertSignal(
                signal_type=self.name.lower(),
                symbol=symbol,
                description=text,
                vpin=m.vpin,
                basis=m.basis,
                obi=m.obi,
                z_score_htf=m.z_htf,
                regime=m.regime
            )
            
            if hasattr(self.gateway, "curation_buffer"):
                self.gateway.curation_buffer.ingest(signal)
                
        except Exception as e:
            self.log.warning(f"Error en curación: {e}")

        # BLOQUE NUEVO — Reactive Router trigger
        try:
            from core.reactive_router import get_router, RouterTrigger
            # Signal already has enriched data, but RouterTrigger needs vpin specifically
            # We reuse 'm' from above
            router = get_router()
            rt = RouterTrigger(
                signal_type=self.name,
                symbol=symbol,
                vpin=m.vpin,
                description=text,
            )
            asyncio.create_task(router.on_signal(rt))
        except Exception as e:
            self.log.warning(f"[ReactiveRouter] Error no crítico: {e}")
