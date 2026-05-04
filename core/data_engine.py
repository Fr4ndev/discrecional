# core/data_engine.py — SHIM (backward compat)
"""
Deprecated: use Core_Intelligence_Hub directly.

Provides a DataEngine class that transparently returns the
IntelligenceHub singleton, so legacy code using DataEngine()
or `async with DataEngine() as engine:` keeps working.
"""
from core.Core_Intelligence_Hub import IntelligenceHub


class DataEngine:
    """
    Backward-compatible shim → IntelligenceHub singleton.

    Supports:
      - DataEngine()                      → returns singleton wrapper
      - async with DataEngine() as eng:   → connects + returns Hub
      - await engine.fetch_ohlcv(...)     → delegates to Hub
    """

    _hub = None

    def __new__(cls, *args, **kwargs):
        obj = object.__new__(cls)
        return obj

    def _get_hub(self):
        if DataEngine._hub is None:
            DataEngine._hub = IntelligenceHub.instance_sync()
            DataEngine._hub._init_internals()
        return DataEngine._hub

    def __getattr__(self, name):
        """Proxy all attribute access to the Hub singleton."""
        return getattr(self._get_hub(), name)

    async def connect(self):
        hub = self._get_hub()
        hub._init_internals()
        await hub.connect()

    async def close(self):
        # Singleton: never close from shim — other components need it
        pass

    async def __aenter__(self):
        hub = self._get_hub()
        hub._init_internals()
        await hub.connect()
        return hub

    async def __aexit__(self, *_):
        # Singleton: do NOT close
        pass
