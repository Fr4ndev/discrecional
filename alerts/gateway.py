#!/usr/bin/env python3
"""
alerts/gateway.py — Centralized Alert Gateway (Extracted from Guardian_Daemon)
═══════════════════════════════════════════════════════════════════════════════
Institutional-grade Telegram dispatcher with:
  - Priority queue (CRITICAL goes first)
  - Deduplication with configurable cooldown
  - Rate limiting (max N messages per minute)
  - Unified formatting header
  - Singleton pattern for process-wide reuse

Usage (standalone — direct send):
    gw = SentinelGateway.instance()
    await gw.dispatch(AlertMessage(source="MyEngine", priority=2, text="..."))

Usage (under Guardian — queued send):
    gw = SentinelGateway.instance(dry_run=True)
    asyncio.create_task(gw.run())   # Start consumer loop
    await gw.dispatch(...)          # Messages go through queue
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional

import httpx

from core.config import settings

logger = logging.getLogger("SentinelGateway")


# ═══════════════════════════════════════════════════════════════════
# ALERT MESSAGE
# ═══════════════════════════════════════════════════════════════════

@dataclass
class AlertMessage:
    source:    str        # Task name (e.g. "IgnitionBridge")
    priority:  int        # 1=CRITICAL, 2=HIGH, 3=MEDIUM, 4=INFO
    text:      str
    dedup_key: str = ""   # Empty = no dedup
    photo:     Optional[bytes] = None  # Optional photo bytes
    timestamp: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════════════════════
# SENTINEL GATEWAY
# ═══════════════════════════════════════════════════════════════════

class SentinelGateway:
    """
    Institutional-grade Telegram dispatcher.

    Features:
      - Priority queue (CRITICAL goes first regardless of order)
      - Deduplication: same dedup_key suppressed for cooldown_seconds
      - Rate limiting: max N messages per minute to avoid Telegram 429
      - Unified formatting header so all alerts look consistent
      - Two modes: queued (under Guardian) or direct (standalone)
      - Photo support: sends text as caption for photos
    """

    MAX_PER_MINUTE   = 10
    DEFAULT_COOLDOWN = 600   # 10 min

    _inst: Optional["SentinelGateway"] = None

    @classmethod
    def instance(cls, **kwargs) -> "SentinelGateway":
        """Get or create the process-wide singleton."""
        if cls._inst is None:
            cls._inst = cls(**kwargs)
        return cls._inst

    def __init__(self, cooldown_seconds: int = DEFAULT_COOLDOWN,
                 dry_run: bool = False):
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._dedup: Dict[str, float] = {}
        self._cooldown = cooldown_seconds
        self._sent_this_minute: deque = deque()
        self._token   = getattr(settings, "telegram_token", "")
        self._chat_id = getattr(settings, "chat_id", "")
        self._topic   = getattr(settings, "topic_id", None)
        self._running = True
        self._consumer_active = False
        self._dry_run = dry_run or os.getenv("DRY_RUN", "0") == "1"

        # Register as singleton if not already set
        if SentinelGateway._inst is None:
            SentinelGateway._inst = self

        # BLOQUE NUEVO — Curation Initialization
        self._loop = asyncio.get_event_loop()
        self.curation_buffer = CurationBuffer(send_fn=self.dispatch_synthetic)

    def dispatch_synthetic(self, text: str) -> None:
        """Helper to dispatch a synthesized pulse message (thread-safe)."""
        def _dispatch():
            asyncio.create_task(self.dispatch(AlertMessage(
                source="BRAIN",
                priority=2, # HIGH
                text=text,
                dedup_key=f"synthetic_pulse_{int(time.time()/CurationBuffer.WINDOW_SECONDS)}" # Unique per window
            )))
        
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(_dispatch)
        else:
            logger.warning("Event loop not running, synthetic pulse dropped.")

    async def dispatch(self, msg: AlertMessage) -> None:
        """Enqueue an alert. Deduplication is checked here."""
        if msg.dedup_key:
            last = self._dedup.get(msg.dedup_key, 0)
            if (time.time() - last) < self._cooldown:
                logger.debug(f"[Gateway] Dedup suppressed: {msg.dedup_key}")
                return

        if self._consumer_active:
            # Queued mode: consumer loop will send it
            await self._queue.put((msg.priority, time.time(), msg))
        else:
            # Direct mode: send immediately (standalone usage)
            await self._send(msg)
            if msg.dedup_key:
                self._dedup[msg.dedup_key] = time.time()

    async def run(self) -> None:
        """Consume alert queue and send to Telegram. Called by Guardian."""
        self._consumer_active = True
        logger.info("📡 SentinelGateway ACTIVE (queued mode)")
        while self._running:
            try:
                _, _, msg = await asyncio.wait_for(
                    self._queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                continue

            if self._rate_limited():
                logger.warning(
                    f"[Gateway] Rate limit hit — re-queuing: {msg.source}")
                await asyncio.sleep(5)
                await self._queue.put((msg.priority, time.time(), msg))
                continue

            await self._send(msg)

            if msg.dedup_key:
                self._dedup[msg.dedup_key] = time.time()

    def _rate_limited(self) -> bool:
        now = time.time()
        cutoff = now - 60
        while self._sent_this_minute and self._sent_this_minute[0] < cutoff:
            self._sent_this_minute.popleft()
        return len(self._sent_this_minute) >= self.MAX_PER_MINUTE

    async def _send(self, msg: AlertMessage) -> None:
        self._sent_this_minute.append(time.time())
        full_text = self._format(msg)

        # TELEGRAM DESACTIVADO (Por petición del usuario)
        # Solo se corren las rutinas en el IDE localmente.
        logger.info(f"[Gateway][LOCAL-ONLY] [{msg.source}]\n{full_text}")
        return

    @staticmethod
    def _format(msg: AlertMessage) -> str:
        priority_icons = {
            1: "🚨", # CRITICAL
            2: "🔥", # HIGH
            3: "⚡", # MEDIUM
            4: "🔍", # INFO
        }
        icon = priority_icons.get(msg.priority, "🔹")
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        
        # Use Markdown for better reliability according to user
        return (
            f"{icon} *SENIOR DESK | {msg.source.upper()}*\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"{msg.text}\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"⏱ `{ts} UTC` | P{msg.priority}"
        )

    def stop(self) -> None:
        self._running = False
        self._consumer_active = False

# ============================================================
# BLOQUE NUEVO — CurationBuffer (Unified Intelligence v1.0)
# NO modifica ninguna clase existente arriba de esta línea
# ============================================================
import threading
import time
from collections import defaultdict
from typing import List, Dict, Any

class AlertSignal:
    """Payload enriquecido de una señal individual del Guardian."""
    def __init__(self, signal_type: str, symbol: str, description: str,
                 z_score_htf: float = 0.0, regime: str = "unknown",
                 vpin: float = 0.0, basis: float = 0.0, obi: float = 0.0,
                 metadata: Dict[str, Any] = None):
        self.signal_type = signal_type
        self.symbol = symbol
        self.description = description
        self.z_score_htf = z_score_htf
        self.regime = regime
        self.vpin = vpin
        self.basis = basis
        self.obi = obi
        self.metadata = metadata or {}
        self.timestamp = time.time()

from core.Core_Intelligence_Hub import VPIN_THRESHOLD, OBI_IGNITION as OBI_THRESHOLD, BASIS_THRESHOLD_PCT as BASIS_THRESHOLD

class CurationBuffer:
    """
    Ventana de 30s que agrupa señales y emite un Pulso Alpha Unificado.
    
    USO:
        buffer = CurationBuffer(send_fn=gateway_instance.send_message)
        buffer.ingest(AlertSignal(...))
    
    REGLA: No instanciar más de una vez por gateway. Es un Singleton de hecho.
    """
    
    # Importados de Core_Intelligence_Hub
    WINDOW_SECONDS  = 30
    
    # Pesos de confluencia para scoring
    SIGNAL_WEIGHTS = {
        "whale":      3,
        "sfp":        2,
        "ict_sweep":  2,
        "level_break":2,
        "spoofing":   1,
        "default":    1,
    }

    def __init__(self, send_fn):
        """
        Args:
            send_fn: callable(text: str) → envía el pulso sintetizado a Telegram.
                     Debe ser la función de envío del gateway existente.
        """
        self._send_fn = send_fn
        self._buffer: List[AlertSignal] = []
        self._lock = threading.Lock()
        self._timer: threading.Timer = None
        self._logger = _get_module_logger()  # usa el logger existente del módulo
    
    def ingest(self, signal: AlertSignal) -> None:
        """Recibe una señal. Inicia (o reinicia) el timer de ventana."""
        with self._lock:
            self._buffer.append(signal)
            self._logger.debug(
                f"[CurationBuffer] +1 señal: {signal.signal_type} / {signal.symbol}"
            )
        self._reset_timer()
    
    # ── Privados ──────────────────────────────────────────────
    
    def _reset_timer(self) -> None:
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self.WINDOW_SECONDS, self._flush)
            self._timer.daemon = True
            self._timer.start()
    
    def _flush(self) -> None:
        with self._lock:
            signals = list(self._buffer)
            self._buffer.clear()
            self._timer = None
        
        if not signals:
            return
        
        pulse = self._synthesize(signals)
        if pulse:
            try:
                # We need to wrap the pulse string into an AlertMessage for the gateway's dispatch or _send
                # However, the prompt says send_fn(pulse). 
                # If send_fn is gateway._send, it expects an AlertMessage.
                # If send_fn is a custom wrapper, we need to be careful.
                self._send_fn(pulse)
            except Exception as e:
                self._logger.error(f"[CurationBuffer] Error enviando pulso: {e}")
    
    def _synthesize(self, signals: List[AlertSignal]) -> str:
        """
        Genera el Veredicto PhD a partir de la confluencia de señales.
        Aplica las Golden Rules antes de publicar.
        """
        if not signals:
            return ""
        
        # Tomar los valores más recientes de métricas clave
        latest = max(signals, key=lambda s: s.timestamp)
        vpin   = latest.vpin
        basis  = latest.basis
        obi    = latest.obi
        symbol = latest.symbol
        regime = latest.regime
        z_htf  = latest.z_score_htf
        
        # === GOLDEN RULES GATE ===
        if vpin < self.VPIN_THRESHOLD:
            self._logger.info(
                f"[CurationBuffer] Pulso bloqueado: VPIN={vpin:.3f} < {self.VPIN_THRESHOLD}"
            )
            return ""
        
        # Scoring de confluencia
        types = [s.signal_type.lower() for s in signals]
        score = sum(self.SIGNAL_WEIGHTS.get(t, self.SIGNAL_WEIGHTS["default"])
                    for t in types)
        
        # Mapa de señales únicas
        unique_types = list(dict.fromkeys(types))
        signal_summary = ", ".join(unique_types)
        
        # Probabilidad cualitativa
        if score >= 7:
            prob_label = "MUY ALTA"
            emoji = "🔴"
        elif score >= 4:
            prob_label = "ALTA"
            emoji = "🟠"
        elif score >= 2:
            prob_label = "MODERADA"
            emoji = "🟡"
        else:
            prob_label = "BAJA"
            emoji = "🟢"
        
        # Contexto macro
        basis_ctx = ""
        if basis < self.BASIS_THRESHOLD:
            basis_ctx = "\n📊 *Basis negativo*: acumulación institucional detectada."
        
        obi_ctx = ""
        if obi >= self.OBI_THRESHOLD:
            obi_ctx = f"\n⚖️ *OBI={obi:.2f}*: dominancia bid confirmada."
        
        # Ensamblado del pulso
        pulse = (
            f"{emoji} *PULSO ALPHA UNIFICADO — {symbol}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 *Confluencia detectada*: {signal_summary}\n"
            f"📈 *Régimen*: {regime} | Z-HTF: {z_htf:+.2f}\n"
            f"☣️ *VPIN (Toxicidad)*: {vpin:.3f}\n"
            f"{basis_ctx}{obi_ctx}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 *Probabilidad de reversión institucional*: **{prob_label}**\n"
            f"_(ventana de síntesis: {len(signals)} señales / {self.WINDOW_SECONDS}s)_"
        )
        
        return pulse


def _get_module_logger():
    """Obtiene el logger existente del módulo gateway, o crea uno seguro."""
    import logging
    # Intenta usar el logger que ya existe en el módulo
    for name in ["gateway", "alerts.gateway", "SentinelGateway", __name__]:
        existing = logging.getLogger(name)
        if existing.handlers:
            return existing
    return logging.getLogger("ccxtv2.curation_buffer")
