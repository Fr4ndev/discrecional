# ccxtv2 Restructuring Plan — Forensic Edition

> **Based on:** Reading all 65 source files, GRAPH_REPORT.md, and 9 prior conversations.
> **Date:** 2026-04-27

---

## 1. Forensic Corrections — What the Graph Got Wrong

The graph report has **744 inferred edges at 62% confidence**. After reading every file, here's what's real vs noise:

### TelegramService (87 edges → actually ~12 real)

The graph inflated `TelegramService` into a God Node. In reality, `alerts/telegram.py` is a **clean 146-line utility** with only `send_photo()` and `send_text()`. It has ZERO business logic.

**The real problem** is that Telegram sending is scattered across **4 independent systems:**

| System | File | How it sends |
|--------|------|-------------|
| `TelegramService` | `alerts/telegram.py` | python-telegram-bot SDK |
| `SentinelGateway` | `Guardian_Daemon.py:105-199` | Raw httpx POST to Telegram API |
| `send_telegram()` | `sfp_advanced_monitor.py:200-213` | Raw requests POST |
| `FundingFeesEngine` | `strategies/funding_fees.py:266` | Imports TelegramService directly |

**Verdict:** The tumor isn't TelegramService itself — it's **4 separate Telegram implementations** that should funnel through ONE gateway.

### IntelligenceHub (60 edges → mostly real)

`IntelligenceHub` is **already well-consolidated** (913 lines). It absorbed DataEngine, ZScoreEngine, FundingFeesEngine internals. It has:
- Singleton pattern ✅
- TTL cache ✅  
- Retry with 429 cooldown ✅
- Typed dataclasses (MarketSnapshot, OBISnapshot, etc.) ✅

**The real problem:** Not everyone uses it:

| Component | Uses Hub? | What it uses instead |
|-----------|----------|---------------------|
| Guardian_Daemon | ✅ Yes | Shared singleton |
| audit_actions.py | ❌ No | `DataEngine` shim (which aliases Hub but creates new instances) |
| absorption_detector.py | ❌ No | `DataEngine` shim |
| eth_liquidity_engine.py | ❌ No | `DataEngine()` — creates standalone instance |
| funding_actions.py | ❌ No | Raw `ccxt` — completely standalone |
| sfp_advanced_monitor.py | ❌ No | `DataEngine` (but Guardian wraps it with Hub) |
| controller.py | ❌ No | `DataEngine()` — creates per-command |

### The Abandoned Bus Refactor

`core/bus/` directory exists but is **completely empty** (only `__pycache__`). Meanwhile, `sensors/registry.py` imports `from core.bus import SignalBus` — **which doesn't exist**. Someone started the event bus refactor and abandoned it. The `sensors/legacy_daemon_sensors.py` file has 9 log-tail sensors that can't work without the bus.

---

## 2. The Gold Map — What Must NOT Be Touched

These are production-grade engines. **Do not refactor their internals:**

| Engine | File | Lines | Why it's gold |
|--------|------|-------|--------------|
| IntelligenceHub | `core/Core_Intelligence_Hub.py` | 913 | PhD microstructure: VPIN, OBI, CVD, Basis, Wall Velocity |
| AbsorptionDetector | `actions/absorption_detector.py` | 301 | Kyle's Lambda, Iceberg detection, VPIN-inspired toxicity |
| Guardian_Daemon | `daemons/Guardian_Daemon.py` | 1011 | 7-task supervisor with BaseSentinelTask, auto-restart |
| SFPAdvancedMonitor | `daemons/sfp_advanced_monitor.py` | 667 | Triple-Layer Audit, HTF trend filter, adaptive polling |
| FundingFeesEngine | `strategies/funding_fees.py` | 564 | Multi-DEX scraping + CCXT fallback + Z-Score anomaly |
| funding_actions.py | `actions/funding_actions.py` | 1204 | Standalone action server endpoints (intentionally isolated) |

> [!CAUTION]
> `funding_actions.py` is **intentionally self-contained** — it creates its own CCXT instances because the sema4ai action server runs in its own process. Do NOT try to make it share IntelligenceHub.

---

## 3. The 4-Phase Surgical Plan

### Phase 1: Unify Telegram (Kill the 4-headed hydra)

**Goal:** All alerts flow through `SentinelGateway` — the best implementation.

**Why SentinelGateway wins:**
- Priority queue (CRITICAL first)
- Deduplication with cooldown
- Rate limiting (10/min)
- Consistent formatting
- Already used by Guardian_Daemon's 7 tasks

**Changes:**

```diff
# 1. Move SentinelGateway to alerts/gateway.py (extract from Guardian_Daemon)
+ alerts/gateway.py          ← SentinelGateway + AlertMessage (extracted)

# 2. Make TelegramService a thin wrapper around SentinelGateway
# alerts/telegram.py — becomes backward-compat shim
- class TelegramService:
-     async def send_text(self, text, ...):
-         await self.bot.send_message(...)
+ class TelegramService:
+     def __init__(self):
+         self._gateway = SentinelGateway.instance()
+     async def send_text(self, text, priority=4, ...):
+         await self._gateway.dispatch(AlertMessage(
+             source="TelegramService", priority=priority, text=text))

# 3. Kill direct Telegram in sfp_advanced_monitor.py
# daemons/sfp_advanced_monitor.py
- def send_telegram(message: str) -> None:
-     requests.post(url, json={...})
+ # Remove entirely — SFPSentinelTask in Guardian already wraps this

# 4. Kill direct TelegramService import in funding_fees.py
# strategies/funding_fees.py
- from alerts.telegram import TelegramService
- tg = TelegramService()
- await tg.send_text(trigger_msg)
+ from alerts.gateway import SentinelGateway, AlertMessage
+ gateway = SentinelGateway.instance()
+ await gateway.dispatch(AlertMessage(source="FundingFees", ...))
```

**Files touched:** 4 files modified, 1 file created. Zero engine logic changed.

---

### Phase 2: Complete the Event Bus

**Goal:** Finish the abandoned `core/bus` refactor. Make engines emit signals, interfaces subscribe.

**Implementation:**

```python
# core/bus.py (new file — simple, no dependencies)
import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List
import time

@dataclass
class Signal:
    """Typed event emitted by engines."""
    kind: str              # "funding_anomaly", "sfp_triggered", "squeeze_detected"
    source: str            # "FundingFeesEngine", "SqueezeMonitor"
    asset: str             # "BTC", "ETH"
    confidence: float      # 0.0 - 1.0
    payload: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

class SignalBus:
    """Process-wide async pub/sub. Singleton."""
    _inst = None

    @classmethod
    def instance(cls):
        if cls._inst is None:
            cls._inst = cls()
        return cls._inst

    def __init__(self):
        self._subs: Dict[str, List[Callable]] = {}

    def subscribe(self, kind: str, handler: Callable[[Signal], Coroutine]):
        self._subs.setdefault(kind, []).append(handler)

    def subscribe_all(self, handler: Callable[[Signal], Coroutine]):
        self._subs.setdefault("*", []).append(handler)

    async def publish(self, signal: Signal):
        for handler in self._subs.get(signal.kind, []):
            asyncio.create_task(handler(signal))
        for handler in self._subs.get("*", []):
            asyncio.create_task(handler(signal))
```

**Wiring into Guardian_Daemon:**

```python
# Guardian_Daemon.py — add bus bridge
class GuardianDaemon:
    def __init__(self):
        self._bus = SignalBus.instance()
        self._gateway = SentinelGateway()
        # Subscribe gateway to ALL signals for Telegram forwarding
        self._bus.subscribe_all(self._signal_to_telegram)

    async def _signal_to_telegram(self, signal: Signal):
        """Bridge: Signal → AlertMessage → Telegram"""
        priority = 2 if signal.confidence > 0.8 else 3
        await self._gateway.dispatch(AlertMessage(
            source=signal.source, priority=priority,
            text=signal.payload.get("message", str(signal)),
            dedup_key=f"{signal.kind}_{signal.asset}",
        ))
```

**Files touched:** 1 new file (`core/bus.py`), Guardian_Daemon wiring, remove empty `core/bus/` directory.

---

### Phase 3: Standardize Hub Usage

**Goal:** Everyone that needs exchange data uses IntelligenceHub singleton. No more standalone DataEngine instances.

**Changes by file:**

#### `audit_actions.py` (action server)
```diff
# The action server needs sync wrappers — use _run_hub_sync from Hub
- from core.data_engine import DataEngine
- engine = DataEngine()
- await engine.connect()
+ from core.Core_Intelligence_Hub import IntelligenceHub, _run_hub_sync

@action(is_consequential=False)
def microstructure_audit(symbol: str = "BTC/USDT:USDT") -> dict:
-   async def _audit():
-       engine = DataEngine()
-       await engine.connect()
-       try: ...
-       finally: await engine.close()
-   return _run_async(_audit())
+   def _audit(hub):
+       return hub.market_snapshot(symbol, ...)  # Hub already has all this
+   return _run_hub_sync(lambda hub: _audit(hub))
```

#### `absorption_detector.py`
```diff
- from core.data_engine import DataEngine
+ from core.Core_Intelligence_Hub import IntelligenceHub

class AbsorptionDetector:
-   def __init__(self, engine: DataEngine):
+   def __init__(self, engine: IntelligenceHub):
        self.engine = engine
    # All method bodies stay IDENTICAL — DataEngine is already a Hub alias
```

#### `eth_liquidity_engine.py`
```diff
class ETHLiquidityEngine:
-   def __init__(self, symbol="ETH/USDT:USDT"):
-       self.engine = DataEngine()
+   def __init__(self, symbol="ETH/USDT:USDT", hub=None):
+       self.hub = hub  # Injected, not created
    async def connect(self):
-       await self.engine.connect()
+       if self.hub is None:
+           self.hub = await IntelligenceHub.instance()
+           await self.hub.connect()
```

#### `controller.py` — Legacy CLI
```diff
# Keep working but use Hub
- async with DataEngine() as engine:
-     results = await heatmap_engine.run(ticker, engine)
+ hub = await IntelligenceHub.instance()
+ await hub.connect()
+ results = await heatmap_engine.run(ticker, hub)
```

> [!IMPORTANT]  
> `funding_actions.py` is **NOT changed** — it runs in a separate sema4ai process and needs its own CCXT connections. This isolation is by design.

---

### Phase 4: File Cleanup

**Goal:** Remove noise from project root, consolidate documentation.

#### Files to move to `legacy_backup/`:
```
direct_audit.py, discovery_audit.py, hybrid_audit_flow.py,
master_audit_v5.py, generate_report.py, get_ranges.py,
market_data_simulator.py, senior_desk_watchdog.py,
test_ccxt.py, test_ele_setup.py, test_fast.py
```

#### JSON artifacts to move to `data/`:
```
*.json (all 50+ JSON files in root) → data/snapshots/
```

#### Docs consolidation:
```
README.md                    ← keep (primary)
README_DEFINITIVO.md         → docs/architecture.md
FLOWS_OPERATING_MANUAL.md    → docs/flows_manual.md
INTELLIGENCE_MANUAL.md       → docs/intelligence.md
SIGNAL_MAPPING.md            → docs/signals.md
All walkthroughs             → docs/walkthroughs/
```

#### Remove dead code:
```
core/bus/           ← empty directory with only __pycache__
core/data_engine.py ← shim, but keep until Phase 3 complete
core/redis_cache.py ← check if used (likely dead)
```

---

## 4. Proposed File Tree (Post-Restructuring)

```
ccxtv2/
├── core/
│   ├── Core_Intelligence_Hub.py   # THE BRAIN (unchanged internals)
│   ├── bus.py                     # NEW: SignalBus pub/sub
│   ├── config.py                  # Settings loader (unchanged)
│   ├── execution_engine.py        # ExecutionEngine + LiquidityAwareStopLoss
│   ├── indicators.py              # adx, atr, ema, etc.
│   └── data_engine.py             # SHIM (kept for backward compat)
│
├── alerts/
│   ├── gateway.py                 # NEW: SentinelGateway (extracted)
│   └── telegram.py                # Thin wrapper → gateway
│
├── daemons/
│   ├── Guardian_Daemon.py         # Master supervisor (uses gateway)
│   ├── sfp_advanced_monitor.py    # SFP v2.2 (remove direct TG)
│   └── level_break_alert.py       # Level break monitor
│
├── strategies/                    # Analysis engines
│   ├── funding_fees.py            # Multi-DEX monitor (uses gateway)
│   ├── eth_liquidity_engine.py    # ELE (uses Hub injection)
│   ├── zscore.py, heatmap.py, orderflow.py, spotdiff.py
│   └── funding_monitor.py
│
├── sensors/                       # Log-tail sensors (uses bus.py)
│   ├── registry.py                # NOW works (bus exists)
│   └── legacy_daemon_sensors.py
│
├── funding_action_server/         # ISOLATED (intentional)
│   └── actions/
│       ├── funding_actions.py     # Standalone CCXT (unchanged)
│       ├── audit_actions.py       # Uses _run_hub_sync
│       └── absorption_detector.py # Uses Hub injection
│
├── config/settings.yaml
├── controller.py                  # CLI (uses Hub)
└── docs/                          # Consolidated documentation
```

---

## 5. Execution Order & Risk Assessment

| Phase | Effort | Risk | Breaking Changes |
|-------|--------|------|-----------------|
| Phase 1: Unify Telegram | 2-3 hours | LOW | None — all existing callers still work |
| Phase 2: Event Bus | 1-2 hours | LOW | None — additive only |
| Phase 3: Hub Usage | 3-4 hours | MEDIUM | audit_actions.py, absorption_detector.py |
| Phase 4: Cleanup | 1 hour | ZERO | File moves only |

> [!TIP]
> **Start with Phase 1.** It's the highest impact with zero risk. The 4 Telegram implementations are the most confusing part of the codebase. Unifying them through SentinelGateway gives you instant rate-limiting, dedup, and priority queuing across ALL components.

---

## 6. What This Does NOT Change

- **Golden Rules thresholds** — VPIN, Basis, CVD, OBI gates are untouched
- **IntelligenceHub internals** — No changes to analysis methods
- **Guardian_Daemon task architecture** — BaseSentinelTask pattern stays
- **funding_actions.py** — Action server isolation preserved
- **SFPAdvancedMonitor logic** — Only removes direct Telegram, logic identical
- **Any strategy engine internals** — ZScore, Heatmap, OrderFlow, SpotDiff untouched
