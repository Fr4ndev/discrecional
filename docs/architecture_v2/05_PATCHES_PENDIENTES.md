# Parches Pendientes — Cycle 5 (Self-Improvement Continuation)
**Generated:** 2026-05-05 | **Status:** DOCUMENTED — No code modified (policy: no machacar)
**Source files affected:** `daemons/Guardian_Daemon.py`, `senior_audit_orchestrator.py`, `funding_action_server/actions/audit_actions.py`, `auto_senior_analyst.py`

---

## PATCH-01: OpportunityTask Division by Zero Guard

**File:** `daemons/Guardian_Daemon.py`
**Lines:** 524-533 (`OpportunityTask._scan_asset()`)
**Severity:** HIGH (FP-04 variant — price=0 → ZeroDivisionError → task crash loop)
**Condition:** `IntelligenceHub.get_price()` returns `0.0` (ticker fetch failed)

### Current code (at line 524):
```python
for sup in asset_levels.get("supports", []):
    if 0 < (price - sup) / price < 0.002:
        proximity_context = f"📍 Price near Support: `${sup:,.2f}`"
        ...
```

### Patch to apply:
```python
if price == 0:
    self.log.debug(f"[{name}] Price unavailable, skipping level proximity check")
    return

for sup in asset_levels.get("supports", []):
    if 0 < (price - sup) / price < 0.002:
        ...
```

---

## PATCH-02: SeniorAuditOrchestrator Class Body Restoration

**File:** `senior_audit_orchestrator.py`
**Lines:** 29-35
**Severity:** CRITICAL (FP-05 — class truncated, missing `__init__` and `execute_all_flows`)
**Condition:** Guardian_Daemon.py line 75 imports this class. If instantiated, crashes.

### Current code (lines 29-35):
```python
class SeniorAuditOrchestrator:
    # ... (__init__ and call_action)

    def calculate_scalp_score(self, asset):
```

### Patch to apply — replace lines 29-35 with:
```python
class SeniorAuditOrchestrator:
    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = f"data/audit_runs/server_audit_{self.timestamp}"
        os.makedirs(self.run_dir, exist_ok=True)
        self.RUN_DIR = self.run_dir
        self.results = {}

    def call_action(self, endpoint, payload):
        url = f"{BASE_URL}/{endpoint}/run"
        try:
            resp = requests.post(url, json=payload, headers=HEADERS, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except (json.JSONDecodeError, TypeError):
                        pass
                return data
            else:
                print(f"[Orchestrator] HTTP {resp.status_code}: {resp.text[:100]}")
                return None
        except requests.Timeout:
            print(f"[Orchestrator] Timeout: {endpoint}")
            return None
        except Exception as e:
            print(f"[Orchestrator] Error: {e}")
            return None

    def execute_all_flows(self):
        # Scalp flows
        for asset in ASSETS:
            self.results[f"scalp_tox_{asset}"] = self.call_action(
                "get-toxicity-index",
                {"symbol": f"{asset}/USDT:USDT", "ob_depth": 20, "trade_limit": 500}
            )
            self.results[f"scalp_audit_{asset}"] = self.call_action(
                "microstructure-audit",
                {"symbol": f"{asset}/USDT:USDT"}
            )
        # Intraday flows
        for asset in ASSETS:
            self.results[f"intraday_basis_{asset}"] = self.call_action(
                "get-basis",
                {"symbol_spot": f"{asset}/USDT", "symbol_perp": f"{asset}/USDT:USDT"}
            )
        self.results["intraday_udc"] = self.call_action(
            "get-ultra-deep-confluence",
            {"assets": ",".join(ASSETS), "depth": 100}
        )
        # Alpha flows
        self.results["sfp_triggers"] = self.call_action(
            "detect-confluence-trigger",
            {"assets": ",".join(ALPHA_ASSETS)}
        )
        self.results["ele_potential"] = self.call_action(
            "eth-ele-audit",
            {"symbol": "ETH/USDT:USDT"}
        )
        print(f"[Orchestrator] Executed {len(self.results)} flows.")
        return True
```

**Post-patch:** Also remove `BASE_URL` duplication (lines 8 and 26).

---

## PATCH-03: Complete to_thread → _internal Refactor

**File:** `funding_action_server/actions/audit_actions.py`
**Lines:** 150-173 (`run_intraday_workflow._routine`)
**Severity:** MEDIUM (safe but suboptimal — creates duplicate Hub instances)

### Current code:
```python
"tactical": {
    "scalp": await asyncio.to_thread(get_tactical_report, assets, "scalp"),
    "swing": await asyncio.to_thread(get_tactical_report, assets, "swing")
},
"udc_walls": await asyncio.to_thread(get_ultra_deep_confluence, assets, 100),
```

### Patch to apply (requires adding `_internal` helpers in `funding_actions.py`):
```python
"tactical": {
    "scalp": await _get_tactical_report_internal(hub, assets, "scalp"),
    "swing": await _get_tactical_report_internal(hub, assets, "swing")
},
"udc_walls": await _get_udc_internal(hub, assets, 100),
```

**Pre-requisite:** Extract `_get_tactical_report_internal` and `_get_udc_internal` from `funding_actions.py` following same pattern as `market_actions.py` → `_get_toxicity_index_internal`.

---

## PATCH-04: Load SYSTEM_PROMPT from External File

**File:** `auto_senior_analyst.py`
**Lines:** 233-260 (hardcoded SYSTEM_PROMPT string)
**Severity:** LOW (maintainability)

### Current code:
```python
SYSTEM_PROMPT = """Eres un Senior Desk Institutional Quantitative Analyst ..."""
```

### Patch to apply — replace with:
```python
def _load_system_prompt() -> str:
    prompt_file = Path("skills/SYSTEM_PROMPT.md")
    if prompt_file.exists():
        return prompt_file.read_text().strip()
    # Fallback to hardcoded default
    return """Eres un Senior Desk Institutional Quantitative Analyst ..."""

SYSTEM_PROMPT = _load_system_prompt()
```

**Benefit:** Prompt can be updated by editing `skills/SYSTEM_PROMPT.md` without code change. Enables prompt iteration across sessions.

---

## PATCH-05: Guard LevelBreakTask Against Price=0

**File:** `daemons/Guardian_Daemon.py`
**Lines:** 818-858 (`LevelBreakTask._cycle()`)
**Severity:** LOW (already partially guarded at line 819)

### Current code (line 819):
```python
price = await self.hub.get_price(sym)
if price == 0: continue
```
✅ Already guarded. No patch needed. This is the correct pattern — `OpportunityTask` should copy it.

---

## Summary

| Patch | File | Severity | Lines to edit | Risk |
|:--|:--|:--|:--|:--|
| PATCH-01 | Guardian_Daemon.py | HIGH | Add 3 lines | Zero — only new guard code |
| PATCH-02 | senior_audit_orchestrator.py | CRITICAL | Replace ~7 lines | Low — class currently broken |
| PATCH-03 | audit_actions.py + funding_actions.py | MEDIUM | ~20 lines | Medium — needs new internal helpers |
| PATCH-04 | auto_senior_analyst.py | LOW | Add ~5 lines | Zero — new file already created |
| PATCH-05 | Guardian_Daemon.py | LOW | 0 lines | Already fixed ✅ |

**Files already created (new):**
- `skills/SYSTEM_PROMPT.md` ✅ — External prompt file for PATCH-04
