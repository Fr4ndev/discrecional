#!/usr/bin/env python3
"""
sensors/base.py — Base Sensor Classes
══════════════════════════════════════════
Abstract base for all sensors. Sensors are lightweight producers that
detect events from various sources (log files, API streams, etc.)
and publish them as Signals on the SignalBus.

Classes:
  - Sensor:        Abstract interface (protocol)
  - BaseSensor:    Common base with name, bus ref, and publish()
  - LogTailSensor: Watches a log file and calls handle_line() for each new line
"""

from __future__ import annotations

import abc
import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from core.bus import SignalBus, Signal

logger = logging.getLogger("Sensors")


# ═══════════════════════════════════════════════════════════════════
# SENSOR PROTOCOL
# ═══════════════════════════════════════════════════════════════════

class Sensor(abc.ABC):
    """Abstract sensor interface."""

    @abc.abstractmethod
    async def start(self) -> None:
        """Begin producing signals."""

    @abc.abstractmethod
    async def stop(self) -> None:
        """Graceful shutdown."""


# ═══════════════════════════════════════════════════════════════════
# BASE SENSOR
# ═══════════════════════════════════════════════════════════════════

class BaseSensor(Sensor):
    """
    Common base for all sensors.

    Provides:
      - Named identity for logging
      - Bus reference for publishing
      - Convenience publish() method that creates a Signal
    """

    def __init__(self, name: str, bus: SignalBus) -> None:
        self.name = name
        self.bus = bus
        self._running = False
        self.log = logging.getLogger(f"Sensor.{name}")

    async def publish(self, kind: str, asset: str = "GENERIC",
                      confidence: float = 0.5,
                      payload: Optional[dict] = None) -> None:
        """Convenience: create and publish a Signal."""
        signal = Signal(
            kind=kind,
            source=self.name,
            asset=asset,
            confidence=confidence,
            payload=payload or {},
        )
        await self.bus.publish(signal)

    async def start(self) -> None:
        self._running = True
        self.log.info(f"🟢 Sensor '{self.name}' started")

    async def stop(self) -> None:
        self._running = False
        self.log.info(f"🔴 Sensor '{self.name}' stopped")


# ═══════════════════════════════════════════════════════════════════
# LOG TAIL SENSOR
# ═══════════════════════════════════════════════════════════════════

class LogTailSensor(BaseSensor):
    """
    Watches a log file for new lines and calls handle_line() for each.

    This is the base class for all legacy daemon sensors that were
    converted from standalone daemons to bus-connected sensors.
    Each subclass overrides handle_line() to parse log output
    and publish typed Signals.
    """

    POLL_INTERVAL = 1.0  # seconds between file polls

    def __init__(self, name: str, bus: SignalBus,
                 log_path: str) -> None:
        super().__init__(name, bus)
        self.log_path = Path(log_path)
        self._last_pos = 0

    async def start(self) -> None:
        await super().start()
        # Seek to end of file if it exists (don't replay history)
        if self.log_path.exists():
            self._last_pos = self.log_path.stat().st_size
        asyncio.create_task(self._tail_loop())

    async def _tail_loop(self) -> None:
        """Poll the log file for new lines."""
        while self._running:
            try:
                if self.log_path.exists():
                    size = self.log_path.stat().st_size
                    if size > self._last_pos:
                        with open(self.log_path, 'r') as f:
                            f.seek(self._last_pos)
                            new_lines = f.readlines()
                            self._last_pos = f.tell()

                        for line in new_lines:
                            line = line.strip()
                            if line:
                                await self.handle_line(line)
                    elif size < self._last_pos:
                        # File was truncated/rotated — reset
                        self._last_pos = 0
            except Exception as e:
                self.log.warning(f"Tail error: {e}")

            await asyncio.sleep(self.POLL_INTERVAL)

    @abc.abstractmethod
    async def handle_line(self, line: str) -> None:
        """Subclasses parse the line and call self.publish()."""
