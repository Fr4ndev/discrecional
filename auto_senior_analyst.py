#!/usr/bin/env python3
"""
auto_senior_analyst.py
═══════════════════════════════════════════════════════════════
Orquestador autónomo: corre rutinas → lee datos reales → DeepSeek → reporte MD.
Uso: python3 auto_senior_analyst.py [--mode omega|scalp|intraday|swing|sfp|full]

Diseñado para el ecosistema CCXTV2 Senior Desk.
Action Server: localhost:8080 (sin autenticación, modo local).
Reportes: reports_history/Dossier_<MODE>_<TIMESTAMP>.md
═══════════════════════════════════════════════════════════════
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────
DEEPSEEK_API_KEY  = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL    = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"

ACTION_SERVER  = "http://localhost:8080/api/actions/funding-action-server"
DATA_DIR       = Path("data")
SNAPSHOTS_DIR  = DATA_DIR / "snapshots"
AUDIT_RUNS_DIR = DATA_DIR / "audit_runs"
SKILLS_DIR     = Path("skills")
REPORTS_DIR    = Path("reports_history")
REPORTS_DIR.mkdir(exist_ok=True)

BTC_SYM = "BTC/USDT:USDT"
ETH_SYM = "ETH/USDT:USDT"
ASSETS  = ["BTC", "ETH"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ANALYST] %(levelname)-8s %(message)s"
)
log = logging.getLogger("auto_analyst")


# ══════════════════════════════════════════════════════════════
# ACTION SERVER CLIENT — Calls reales a los endpoints verificados
# ══════════════════════════════════════════════════════════════

class ActionClient:
    """Cliente HTTP para el funding-action-server local."""

    def __init__(self, base_url: str = ACTION_SERVER, timeout: int = 90):
        self.base_url = base_url
        self.timeout = timeout
        self.results: Dict[str, Any] = {}

    async def call(self, endpoint: str, payload: dict, key: str) -> Optional[dict]:
        """POST a un endpoint del action server y almacena el resultado."""
        url = f"{self.base_url}/{endpoint}/run"
        log.info(f"  📡 POST {endpoint} → {key}")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # El action server a veces retorna strings JSON-encoded
                    if isinstance(data, str):
                        try:
                            data = json.loads(data)
                        except (json.JSONDecodeError, TypeError):
                            pass
                    self.results[key] = data
                    log.info(f"  ✅ {key} OK")
                    return data
                else:
                    log.warning(f"  ⚠️ {endpoint}: HTTP {resp.status_code}")
                    return None
        except httpx.TimeoutException:
            log.warning(f"  ⏱️ {endpoint}: timeout ({self.timeout}s)")
            return None
        except Exception as e:
            log.error(f"  ❌ {endpoint}: {e}")
            return None

    # ── Flow Runners ──────────────────────────────────────────

    async def flow_scalp(self):
        """FLOW-SCALP: Toxicity + Microstructure para BTC y ETH."""
        log.info("⚡ FLOW-SCALP — Micro-Trend Explosion")
        for asset in ASSETS:
            sym = f"{asset}/USDT:USDT"
            await self.call("get-toxicity-index",
                {"symbol": sym, "ob_depth": 20, "trade_limit": 500},
                f"tox_{asset}")
            await self.call("microstructure-audit",
                {"symbol": sym},
                f"micro_{asset}")

    async def flow_intraday(self):
        """FLOW-INTRADAY: Basis + UDC + Tactical."""
        log.info("📅 FLOW-INTRADAY — Session Capture")
        for asset in ASSETS:
            await self.call("get-basis",
                {"symbol_spot": f"{asset}/USDT", "symbol_perp": f"{asset}/USDT:USDT"},
                f"basis_{asset}")
        await self.call("get-ultra-deep-confluence",
            {"assets": ",".join(ASSETS), "depth": 100},
            "udc")
        await self.call("get-tactical-report",
            {"assets": ",".join(ASSETS), "strategy": "scalp"},
            "tactical_scalp")

    async def flow_swing(self):
        """FLOW-SWING: Full snapshot + Swing tactical."""
        log.info("🏗️ FLOW-SWING — Regime Change Detection")
        await self.call("get-full-market-snapshot",
            {"assets": ",".join(ASSETS), "ob_depth": 50},
            "full_snapshot")
        await self.call("get-tactical-report",
            {"assets": ",".join(ASSETS), "strategy": "swing"},
            "tactical_swing")

    async def flow_alpha(self):
        """ALPHA: SFP Confluence + ELE Transition."""
        log.info("🔥 ALPHA — Institutional Triggers")
        await self.call("detect-confluence-trigger",
            {"assets": "BTC,ETH,SOL,HYPE"},
            "sfp_triggers")
        await self.call("eth-ele-audit",
            {"symbol": ETH_SYM},
            "ele_audit")

    async def flow_ob_walls(self):
        """OB Walls para niveles clave."""
        log.info("🧱 OB WALLS — Liquidity Mapping")
        for asset in ASSETS:
            await self.call("get-ob-walls",
                {"symbol": f"{asset}/USDT:USDT", "depth": 50},
                f"walls_{asset}")

    # ── Persist raw data ──────────────────────────────────────

    def save_raw(self, run_id: str):
        """Guarda todos los resultados crudos en audit_runs/."""
        run_dir = AUDIT_RUNS_DIR / f"run_{run_id}"
        run_dir.mkdir(parents=True, exist_ok=True)
        for key, data in self.results.items():
            fpath = run_dir / f"{key}.json"
            with open(fpath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        log.info(f"💾 Datos crudos guardados en {run_dir}/ ({len(self.results)} archivos)")


# ══════════════════════════════════════════════════════════════
# MODES — Configuración de cada tipo de análisis
# ══════════════════════════════════════════════════════════════

MODES = {
    "omega": {
        "label": "OMEGA — Brutal Integrated Analysis",
        "flows": ["scalp", "intraday", "swing", "alpha"],
        "depth": "full",
    },
    "scalp": {
        "label": "SCALP — Micro-Trend Explosion",
        "flows": ["scalp"],
        "depth": "micro",
    },
    "intraday": {
        "label": "INTRADAY — Session Capture & Confluence",
        "flows": ["scalp", "intraday"],
        "depth": "session",
    },
    "swing": {
        "label": "SWING — Regime Change Detection",
        "flows": ["scalp", "intraday", "swing"],
        "depth": "macro",
    },
    "sfp": {
        "label": "SFP — Institutional Reversal Scan",
        "flows": ["scalp", "alpha"],
        "depth": "reversal",
    },
    "full": {
        "label": "FULL AUDIT — 360° Institutional Dossier",
        "flows": ["scalp", "intraday", "swing", "alpha", "ob_walls"],
        "depth": "full",
    },
}


# ══════════════════════════════════════════════════════════════
# SKILLS LOADER
# ══════════════════════════════════════════════════════════════

def load_skills(max_chars: int = 4000) -> str:
    """Carga las skills relevantes como contexto para DeepSeek."""
    priority_files = [
        "FLOWS_OPERATING_MANUAL.md",
        "FLOW_OPERATING.md",
        "INTELLIGENCE_MANUAL.md",
    ]
    combined = []
    total = 0
    for fname in priority_files:
        fpath = SKILLS_DIR / fname
        if fpath.exists() and total < max_chars:
            content = fpath.read_text()
            take = min(len(content), max_chars - total)
            combined.append(f"--- SKILL: {fname} ---\n{content[:take]}")
            total += take
    return "\n\n".join(combined)


# ══════════════════════════════════════════════════════════════
# PATCH-04 (Cycle 5): Load SYSTEM_PROMPT from skills/SYSTEM_PROMPT.md
# with hardcoded fallback. Prompt can evolve without code change.
# ══════════════════════════════════════════════════════════════

def _load_system_prompt() -> str:
    prompt_file = Path("skills/SYSTEM_PROMPT.md")
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8").strip()
    # Fallback — keep in sync with skills/SYSTEM_PROMPT.md
    return """Eres un Senior Desk Institutional Quantitative Analyst especializado en
microestructura de mercado cripto. Tu función es producir dossiers de alta convicción
suprimiendo el ruido retail y enfocándote en desequilibrios institucionales.

REGLAS DE DECISIÓN INMUTABLES (del FLOWS_OPERATING_MANUAL):
- VPIN (Toxicity Index) > 0.62: condición mínima para cualquier setup. Por debajo = "Retail Soup" = NO EXECUTION.
- OBI (Order Book Imbalance D20) > ±0.40: presión de bloque institucional confirmada.
- Absorption Rate > 0.60: Icebergs activos, el smart money está absorbiendo.
- Basis < -0.05%: Spot Premium = acumulación institucional stealth.
- Basis > +0.05%: Perp FOMO = distribución — reducir sizing.
- Z-Score HTF > +1.5: mercado sobreextendido — evitar longs.
- Z-Score HTF < -1.5: oversold institucional — alta probabilidad de reversión.
- CVD Acceleration: debe confirmar la dirección del OBI, divergencia = risk-flip.
- Kyle's Lambda bajo = mercado deep y eficiente; alto = slippage y illiquidity.

FRAMEWORK DE DECISIÓN:
- ❌ NO TRADE: toxicidad < 0.62 O OBI neutro (±0.20).
- 🟡 GO PARTIAL: OBI + CVD alineados pero Basis neutral.
- ✅ GO FULL: VPIN > 0.62 + Absorción en muros + SFP confirmado o Basis extreme.

FORMATO OBLIGATORIO:
1. Usa Markdown con emojis institucionales.
2. Datos primero, narrativa después. CADA afirmación respaldada por su métrica concreta.
3. Tono: institucional, no retail. Sin "podría" ni "tal vez" ni "posiblemente".
4. Incluye una tabla resumen por asset con las métricas clave.
5. Genera un SETUP concreto si hay confluencia (entry, invalidation, targets).
6. Termina con: "CONVICTION LEVEL: [BAJO/MEDIO/ALTO/MUY ALTO]"
"""

SYSTEM_PROMPT = _load_system_prompt()


def build_user_prompt(mode_label: str, data: dict, skill_ctx: str) -> str:
    """Construye el prompt con los datos reales del mercado."""
    data_str = json.dumps(data, indent=2, default=str)
    # Limitar para no exceder contexto (~16k tokens de data max)
    if len(data_str) > 14000:
        data_str = data_str[:14000] + "\n... [truncated for token optimization]"

    return f"""## MISIÓN: {mode_label}
Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

## DATOS REALES DEL MERCADO (JSON de los endpoints del action-server):
```json
{data_str}
```

## CONTEXTO OPERACIONAL (Skills del Senior Desk):
{skill_ctx[:2000]}

## INSTRUCCIONES ESPECÍFICAS:
1. Analiza TODOS los datos JSON — son datos REALES del exchange Hyperliquid, no simulados.
2. Extrae y reporta explícitamente: VPIN/Toxicity, OBI, Basis%, Z-Scores, CVD, Absorption, Iceberg Score.
3. Aplica el Decision Framework del FLOWS_OPERATING_MANUAL estrictamente.
4. Para CADA asset (BTC, ETH), produce:
   - Tabla de métricas clave vs umbrales.
   - Veredicto individual (NO TRADE / GO PARTIAL / GO FULL).
   - Setup concreto con Entry / Invalidación / Targets SI hay confluencia.
5. Si detectas ELE Transition activa en ETH, destácalo con su propia sección.
6. Si detectas SFP triggers, analiza la calidad del sweep.
7. Cierra con un VEREDICTO GLOBAL del mercado y CONVICTION LEVEL."""


async def call_deepseek(user_prompt: str) -> Optional[str]:
    """Llama a DeepSeek API y retorna el análisis como string."""
    if not DEEPSEEK_API_KEY:
        log.error("❌ DEEPSEEK_API_KEY no encontrada en .env")
        return None

    log.info(f"🧠 Llamando a DeepSeek ({DEEPSEEK_MODEL})...")
    t0 = time.time()

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 3000,
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                DEEPSEEK_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            elapsed = time.time() - t0
            tokens_used = result.get("usage", {})
            log.info(f"✅ DeepSeek respondió en {elapsed:.1f}s "
                     f"(prompt: {tokens_used.get('prompt_tokens', '?')}, "
                     f"completion: {tokens_used.get('completion_tokens', '?')})")
            return content
    except httpx.HTTPStatusError as e:
        log.error(f"❌ DeepSeek HTTP error: {e.response.status_code} — {e.response.text[:300]}")
        return None
    except Exception as e:
        log.error(f"❌ DeepSeek error: {e}")
        return None


# ══════════════════════════════════════════════════════════════
# REPORT GENERATION
# ══════════════════════════════════════════════════════════════

def save_report(mode: str, label: str, analysis: str, data: dict) -> Path:
    """Guarda el dossier final en reports_history/ con timestamp."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = REPORTS_DIR / f"Dossier_{mode.upper()}_{ts}.md"

    # Extraer métricas para header del reporte
    def _extract(keys: list, default="N/A"):
        for obj in data.values():
            if isinstance(obj, dict):
                for k in keys:
                    if k in obj:
                        return obj[k]
                # Check nested (e.g. toxicity.index, microstructure.obi_20)
                for v in obj.values():
                    if isinstance(v, dict):
                        for k in keys:
                            if k in v:
                                return v[k]
        return default

    vpin_val   = _extract(["index", "tox_score", "toxicity_index"])
    obi_val    = _extract(["obi_20", "obi_current", "obi"])
    basis_val  = _extract(["basis_pct"])
    regime_val = _extract(["regime", "market_regime", "verdict"])

    report = f"""# 🏛️ {label}
**Timestamp:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
**Mode:** `{mode}` | **VPIN:** `{vpin_val}` | **OBI:** `{obi_val}` | **Basis:** `{basis_val}%` | **Régimen:** `{regime_val}`

---

{analysis}

---
*Generado por auto_senior_analyst.py | CCXTV2 Unified Intelligence | DeepSeek {DEEPSEEK_MODEL}*
"""
    filename.write_text(report, encoding="utf-8")
    log.info(f"📄 Reporte guardado: {filename}")
    return filename


# ══════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR
# ══════════════════════════════════════════════════════════════

async def ensure_server_up() -> bool:
    """Verifica que el action server esté corriendo."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get("http://localhost:8080/")
            return resp.status_code == 200
    except Exception:
        return False


async def run(mode: str) -> None:
    config = MODES.get(mode)
    if not config:
        log.error(f"Modo '{mode}' no válido. Opciones: {list(MODES.keys())}")
        sys.exit(1)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    log.info(f"\n{'═'*60}")
    log.info(f"  🏛️  CCXTV2 AUTO SENIOR ANALYST")
    log.info(f"  📋  {config['label']}")
    log.info(f"  ⏰  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    log.info(f"{'═'*60}\n")

    # ── Pre-check: Action Server ──────────────────────────────
    server_up = await ensure_server_up()
    if not server_up:
        log.warning("⚠️ Action Server no responde. Intentando arrancar...")
        # Lanzar en background para evitar timeout (bootstrap RCC tarda 30-90s)
        subprocess.Popen(
            ["bash", "manage.sh", "start"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        log.info("⏳ Esperando bootstrap del Action Server (máx 90s)...")
        for i in range(30):  # 30 intentos x 3s = 90s max
            await asyncio.sleep(3)
            server_up = await ensure_server_up()
            if server_up:
                log.info(f"✅ Action Server online (tardó ~{(i+1)*3}s)")
                break
            log.info(f"  ⏳ Intento {i+1}/30...")
        if not server_up:
            log.error("❌ Action Server no arrancó en 90s. Abortando.")
            sys.exit(1)

    log.info("✅ Action Server online\n")

    # ── STEP 1: Ejecutar flows ────────────────────────────────
    ac = ActionClient()
    flow_map = {
        "scalp":    ac.flow_scalp,
        "intraday": ac.flow_intraday,
        "swing":    ac.flow_swing,
        "alpha":    ac.flow_alpha,
        "ob_walls": ac.flow_ob_walls,
    }

    for flow_name in config["flows"]:
        fn = flow_map.get(flow_name)
        if fn:
            await fn()
            await asyncio.sleep(1)  # Breathing room entre flows

    if not ac.results:
        log.error("❌ Ningún endpoint devolvió datos. Verifica el Action Server.")
        sys.exit(1)

    log.info(f"\n📊 Datos capturados: {len(ac.results)} endpoints\n")

    # Persistir datos crudos
    ac.save_raw(ts)

    # ── STEP 2: Cargar skills ─────────────────────────────────
    skill_ctx = load_skills()

    # ── STEP 3: DeepSeek Analysis ─────────────────────────────
    user_prompt = build_user_prompt(config["label"], ac.results, skill_ctx)
    analysis = await call_deepseek(user_prompt)

    if not analysis:
        log.warning("⚠️ DeepSeek no respondió. Generando reporte con datos crudos.")
        # Fallback: reporte determinístico básico
        analysis = "## ⚠️ DeepSeek no disponible — Datos crudos\n\n"
        for key, val in ac.results.items():
            analysis += f"### {key}\n```json\n{json.dumps(val, indent=2, default=str)[:800]}\n```\n\n"

    # ── STEP 4: Guardar reporte ───────────────────────────────
    report_path = save_report(mode, config["label"], analysis, ac.results)

    log.info(f"\n{'═'*60}")
    log.info(f"  ✅ ANÁLISIS COMPLETO")
    log.info(f"  📄 {report_path}")
    log.info(f"  📊 Endpoints procesados: {len(ac.results)}")
    log.info(f"{'═'*60}\n")

    # Imprimir en consola el reporte completo para captura del controlador
    print("\n" + "=" * 60)
    print(analysis)
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="CCXTV2 Auto Senior Analyst — DeepSeek-powered institutional dossiers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modos disponibles:
  omega     Auditoría brutal integrada (Scalp+Intraday+Swing+Alpha)
  scalp     Micro-trend: toxicity + microstructure
  intraday  Sesión: scalp + basis + UDC + tactical
  swing     Régimen: scalp + intraday + full snapshot
  sfp       Reversión institucional: scalp + SFP triggers
  full      360° completo: todos los flows + OB walls

Ejemplos:
  python3 auto_senior_analyst.py --mode omega
  python3 auto_senior_analyst.py -m sfp
  python3 auto_senior_analyst.py -m full
        """
    )
    parser.add_argument(
        "--mode", "-m",
        default="omega",
        choices=list(MODES.keys()),
        help="Modo de análisis (default: omega)"
    )
    args = parser.parse_args()
    asyncio.run(run(args.mode))


if __name__ == "__main__":
    main()
