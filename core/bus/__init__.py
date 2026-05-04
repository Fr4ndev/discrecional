#!/usr/bin/env python3
"""
core/bus/__init__.py — Process-Wide Async Signal Bus
════════════════════════════════════════════════════════
Lightweight pub/sub for decoupling engines from interfaces.

Engines PUBLISH typed Signals (e.g. "sfp_triggered", "funding_anomaly").
Interfaces SUBSCRIBE to signal kinds and react (e.g. Telegram, Dashboard).

Design:
  - Zero external dependencies (stdlib only)
  - Singleton pattern (process-wide)
  - Wildcard subscriber ("*") receives ALL signals
  - Fire-and-forget: publish() never blocks the caller
  - Thread-safe for mixed sync/async usage

Usage:
    from core.bus import SignalBus, Signal

    bus = SignalBus.instance()
    bus.subscribe("sfp_triggered", my_handler)
    bus.subscribe_all(my_catch_all)
    await bus.publish(Signal(kind="sfp_triggered", source="SFP_v2.2",
                             asset="BTC", confidence=0.85))
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger("SignalBus")


# ═══════════════════════════════════════════════════════════════════
# SIGNAL — Typed event emitted by engines
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Signal:
    """
    Immutable event emitted by any engine/sensor.

    Attributes:
        kind:       Event type (e.g. "funding_anomaly", "sfp_triggered")
        source:     Origin engine name (e.g. "FundingFeesEngine", "SFP_v2.2")
        asset:      Ticker symbol (e.g. "BTC", "ETH", "GENERIC")
        confidence: Signal confidence 0.0 - 1.0
        payload:    Arbitrary data dict for downstream consumers
        timestamp:  UTC epoch seconds (auto-filled)
    """
    kind:       str
    source:     str
    asset:      str           = "GENERIC"
    confidence: float         = 0.5
    payload:    dict          = field(default_factory=dict)
    timestamp:  float         = field(default_factory=time.time)

    def __str__(self) -> str:
        return (f"Signal({self.kind} | {self.source} | {self.asset} "
                f"| conf={self.confidence:.2f})")


# ═══════════════════════════════════════════════════════════════════
# SIGNAL BUS — Async Pub/Sub Singleton
# ═══════════════════════════════════════════════════════════════════

# Type alias for handler coroutines
SignalHandler = Callable[[Signal], Coroutine[Any, Any, None]]


class SignalBus:
    """
    Process-wide async pub/sub bus.

    Features:
      - Topic-based subscription by signal kind
      - Wildcard ("*") subscription for catch-all consumers
      - Fire-and-forget publish (handlers run as tasks)
      - Error isolation: one handler crash doesn't affect others
      - Signal history (last N signals) for late joiners
    """

    _inst: Optional["SignalBus"] = None
    HISTORY_SIZE = 100

    @classmethod
    def instance(cls) -> "SignalBus":
        """Get or create the process-wide singleton."""
        if cls._inst is None:
            cls._inst = cls()
        return cls._inst

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing only)."""
        cls._inst = None

    def __init__(self) -> None:
        self._subs: Dict[str, List[SignalHandler]] = {}
        self._history: List[Signal] = []
        self._total_published = 0
        self._total_delivered = 0

        # Register as singleton
        if SignalBus._inst is None:
            SignalBus._inst = self

    # ── Subscribe ─────────────────────────────────────────────

    def subscribe(self, kind: str, handler: SignalHandler) -> None:
        """Subscribe to a specific signal kind."""
        self._subs.setdefault(kind, []).append(handler)
        logger.debug(f"[Bus] Subscribed to '{kind}': {handler.__qualname__}")

    def subscribe_all(self, handler: SignalHandler) -> None:
        """Subscribe to ALL signals (wildcard)."""
        self._subs.setdefault("*", []).append(handler)
        logger.debug(f"[Bus] Wildcard subscriber: {handler.__qualname__}")

    def subscribe_many(self, kinds: List[str], handler: SignalHandler) -> None:
        """Subscribe to multiple signal kinds at once."""
        for kind in kinds:
            self.subscribe(kind, handler)

    # ── Publish ───────────────────────────────────────────────

    async def publish(self, signal: Signal) -> None:
        """
        Publish a signal to all matching subscribers.
        Handlers run as fire-and-forget tasks (non-blocking).
        """
        self._total_published += 1

        # Store in history ring buffer
        self._history.append(signal)
        if len(self._history) > self.HISTORY_SIZE:
            self._history = self._history[-self.HISTORY_SIZE:]

        # Collect all matching handlers
        handlers = list(self._subs.get(signal.kind, []))
        handlers.extend(self._subs.get("*", []))

        if not handlers:
            logger.debug(f"[Bus] No subscribers for: {signal}")
            return

        for handler in handlers:
            self._total_delivered += 1
            asyncio.create_task(self._safe_dispatch(handler, signal))

    async def _safe_dispatch(self, handler: SignalHandler,
                             signal: Signal) -> None:
        """Run handler with error isolation."""
        try:
            await handler(signal)
        except Exception as e:
            logger.error(
                f"[Bus] Handler {handler.__qualname__} failed on "
                f"{signal.kind}: {e}", exc_info=True)

    # ── Query ─────────────────────────────────────────────────

    @property
    def stats(self) -> dict:
        """Bus statistics for monitoring."""
        return {
            "total_published": self._total_published,
            "total_delivered": self._total_delivered,
            "subscribers": {k: len(v) for k, v in self._subs.items()},
            "history_size": len(self._history),
        }

    def recent(self, kind: Optional[str] = None,
               limit: int = 10) -> List[Signal]:
        """Get recent signals, optionally filtered by kind."""
        signals = self._history
        if kind:
            signals = [s for s in signals if s.kind == kind]
        return signals[-limit:]

    def get_recent(self, kind: str, asset: str, window: int = 30) -> Optional[Signal]:
        """Query for a specific signal within a time window (seconds)."""
        now = time.time()
        for s in reversed(self._history):
            if s.kind == kind and s.asset == asset:
                if (now - s.timestamp) <= window:
                    return s
        return None
