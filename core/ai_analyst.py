import json
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger("ccxtv2.ai_analyst")

DATA_DIR   = Path("data")
SKILLS_DIR = Path("skills")

# Mapa de comando → archivos JSON relevantes + skill .md a usar
ANALYSIS_PROFILES = {
    "full_audit": {
        "jsons": [
            "snapshots/scalp_tox_btc.json", "snapshots/scalp_audit_btc.json",
            "snapshots/intraday_basis_btc.json", "snapshots/intraday_udc.json",
            "snapshots/ele_potential.json"
        ],
        "skills": ["FLOW_OPERATING.md", "FLOWS_OPERATING_MANUAL.md"],
        "label": "FULL AUDIT — Comprehensive Institutional Analysis",
    },
    "omega": {
        "jsons":  ["final_udc.json", "pulse_tox_btc.json", "htf_zscores.json"],
        "skills":  ["FLOW_OPERATING.md", "FLOWS_OPERATING_MANUAL.md"],
        "label":  "OMEGA — Brutal Integrated Analysis",
    },
    "turbo": {
        "jsons":  ["snapshots/turbo_snapshot.json", "snapshots/turbo_tox_btc.json"],
        "skills":  ["INTELLIGENCE_MANUAL.md", "FLOWS_OPERATING_MANUAL.md"],
        "label":  "TURBO — Triple Layer Audit",
    },
    "sfp": {
        "jsons":  ["snapshots/sfp_triggers.json", "snapshots/sfp_tox_btc.json", "snapshots/sfp_depth_btc.json"],
        "skills":  ["INTELLIGENCE_MANUAL.md", "FLOWS_OPERATING_MANUAL.md"],
        "label":  "SFP — Institutional Reversal Audit",
    },
    "scalp": {
        "jsons":  ["snapshots/scalp_tox_btc.json", "snapshots/scalp_audit_btc.json", "snapshots/scalp_walls_btc.json"],
        "skills":  ["FLOW_OPERATING.md", "FLOWS_OPERATING_MANUAL.md"],
        "label":  "SCALP — Microstructure Alpha",
    },
    "intraday": {
        "jsons":  ["snapshots/intraday_basis_btc.json", "snapshots/intraday_tactical_scalp.json", "snapshots/intraday_udc.json"],
        "skills":  ["FLOW_OPERATING.md", "FLOWS_OPERATING_MANUAL.md"],
        "label":  "INTRADAY — Session Capture",
    },
    "swing": {
        "jsons":  ["snapshots/swing_zscore.json"],
        "skills":  ["FLOW_OPERATING.md", "FLOWS_OPERATING_MANUAL.md"],
        "label":  "SWING — Regime Change",
    },
    "alpha": {
        "jsons":  ["snapshots/turbo_snapshot.json", "snapshots/intraday_udc.json", "snapshots/turbo_tox_btc.json"],
        "skills":  ["FLOW_OPERATING.md", "FLOWS_OPERATING_MANUAL.md"],
        "label":  "ALPHA — Hybrid Master Verdict",
    },
    "ele_audit": {
        "jsons":  ["snapshots/ele_potential.json", "snapshots/eth_walls.json", "snapshots/eth_basis.json"],
        "skills":  ["FLOW_OPERATING.md", "microstructure-expert.md"],
        "label":  "ELE — ETH Transition Audit",
    },
    "ignition": {
        "jsons":  ["snapshots/alpha_snapshot.json"],
        "skills":  ["FLOW_OPERATING.md", "FLOWS_OPERATING_MANUAL.md"],
        "label":  "IGNITION — Market Momentum Audit",
    },
    "decision_matrix": {
        "jsons":  ["final_udc.json", "pulse_tox_btc.json", "zscore_elite_btc.json"],
        "skills":  ["FLOW_OPERATING.md", "FLOWS_OPERATING_MANUAL.md"],
        "label":  "DECISION MATRIX — Confluence Audit",
    },
}

from core.Core_Intelligence_Hub import VPIN_THRESHOLD, OBI_IGNITION as OBI_THRESHOLD, BASIS_THRESHOLD_PCT as BASIS_THRESHOLD

# Golden Rules (inmutables — importados del Hub)
# VPIN_THRESHOLD  = 0.62
# BASIS_THRESHOLD = -0.05 (PCT)
# OBI_THRESHOLD   = 0.40


from core.ai_orchestrator import get_orchestrator

class AIAnalyst:
    """
    Genera Veredictos PhD leyendo JSONs reales de data/ y aplicando
    las reglas de los skills .md como lógica fundacional.
    """

    async def analyze(self, profile_name: str, use_ai: bool = False) -> str:
        profile = ANALYSIS_PROFILES.get(profile_name)
        if not profile:
            return f"⚠️ Perfil '{profile_name}' no encontrado."

        # 1. Cargar JSONs reales
        data = self._load_jsons(profile["jsons"])

        # 2. Cargar skill context (Múltiples skills soportadas)
        skill_ctx = self._load_skills(profile.get("skills", []))

        # 3. Decision Path: AI or Deterministic
        if use_ai:
            orchestrator = get_orchestrator()
            if orchestrator.is_enabled:
                # Token Optimization: Filter key fields for AI
                optimized_data = self._optimize_for_ai(data)
                return await orchestrator.analyze_market(profile["label"], optimized_data, skill_ctx)
            else:
                logger.warning("AI Orchestrator disabled. Falling back to deterministic analysis.")

        # 4. Deterministic logic (Original PhD logic)
        return self._deterministic_analysis(profile, data)

    def _optimize_for_ai(self, data: Dict) -> Dict:
        """Filtra solo los campos clave para ahorrar tokens."""
        optimized = {}
        for key, content in data.items():
            if not isinstance(content, dict): 
                optimized[key] = content
                continue
            
            # Sub-selección de campos críticos
            subset = {}
            for field in ["toxicity_index", "obi", "basis", "basis_pct", "cvd", "verdict", "obi_current", "senior_verdict", "score", "potential"]:
                if field in content:
                    subset[field] = content[field]
            
            # Caso especial para resultados de Robocorp Action Server
            if "result" in content:
                res = content["result"]
                if isinstance(res, dict):
                    subset["result_summary"] = {k: v for k, v in res.items() if k in ["verdict", "score", "bias", "toxicity"]}
                else:
                    subset["result"] = res
            
            optimized[key] = subset if subset else content
        return optimized

    def _deterministic_analysis(self, profile, data) -> str:
        # Extraer métricas
        vpin   = self._get(data, ["vpin","toxicity","tox_score","toxicity_index"], 0.0)
        basis  = self._get(data, ["basis","basis_pct"], 0.0)
        obi    = self._get(data, ["obi","order_book_imbalance"], 0.0)
        udc    = self._get(data, ["udc","udc_score","delta_score"], None)
        regime = self._get(data, ["regime","market_regime","htf_regime"], "unknown")
        z_htf  = self._get(data, ["z_score_htf","htf_z","zscore_htf"], 0.0)
        z_d    = self._get(data, ["z_daily","z_score_daily"], 0.0)
        z_w    = self._get(data, ["z_weekly","z_score_weekly"], 0.0)

        # 4. Gate PhD
        if vpin < VPIN_THRESHOLD:
            return (
                f"🚫 *{profile['label']}*\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"☣️ VPIN={vpin:.3f} — Entorno tóxico insuficiente.\n"
                f"Ejecución bloqueada hasta VPIN ≥ {VPIN_THRESHOLD}."
            )

        # 5. Señales confirmadas
        confirmed = []
        warnings  = []

        if basis < BASIS_THRESHOLD:
            confirmed.append(f"📊 Basis={basis*100:.4f}% → Acumulación institucional")
        if obi >= OBI_THRESHOLD:
            confirmed.append(f"⚖️ OBI={obi:.3f} → Dominancia bid confirmada")
        if udc is not None:
            try:
                udc_f = float(udc)
                direction = "ALCISTA" if udc_f > 0 else "BAJISTA"
                confirmed.append(f"📦 UDC={udc_f:+.4f} → Presión {direction}")
            except: pass
        if abs(z_htf) > 1.5:
            tag = "SOBREEXTENDIDO" if z_htf > 0 else "OVERSOLD INSTITUCIONAL"
            confirmed.append(f"📐 Z-HTF={z_htf:+.2f} → {tag}")
        if abs(z_d) > 2.0:
            warnings.append(f"⚡ Z-Daily={z_d:+.2f} → Extremo estadístico")
        if abs(z_w) > 2.0:
            warnings.append(f"🌊 Z-Weekly={z_w:+.2f} → Régimen semanal crítico")

        # 6. Sizing regime
        if regime == "accumulation":
            sizing = "Sizing máximo permitido. Régimen de acumulación activo."
        elif regime == "distribution":
            sizing = "Sizing reducido 50%. Régimen de distribución — evitar longs."
        else:
            sizing = "Confirmar régimen antes de sizing. Datos insuficientes."

        # 7. Setup Generation (PhD Brute Force)
        setup_block = ""
        price = self._get(data, ["price", "last_price", "mark_price", "last"], 0.0)
        
        if price > 0:
            bias = "NEUTRAL"
            # Confluence Logic for Setup
            if vpin >= VPIN_THRESHOLD:
                if (basis < BASIS_THRESHOLD or obi > OBI_THRESHOLD or (udc is not None and float(udc) > 0)):
                    bias = "LONG"
                elif (basis > abs(BASIS_THRESHOLD) or obi < -OBI_THRESHOLD or (udc is not None and float(udc) < 0)):
                    bias = "SHORT"
            
            if bias == "LONG":
                setup_block = (
                    f"\n🔥 **SETUP: LONG AGGRESSIVE (Trap/Absorp)**\n"
                    f"🎯 **Entry**: `{price:,.1f}`\n"
                    f"🛑 **Invalidación**: `{price*0.994:,.1f}`\n"
                    f"🏁 **Targets**: `{price*1.012:,.1f}` (TP1) | `{price*1.028:,.1f}` (TP2)\n"
                )
            elif bias == "SHORT":
                setup_block = (
                    f"\n🏹 **SETUP: SHORT SCALP (Exhaustion)**\n"
                    f"🎯 **Entry**: `{price:,.1f}`\n"
                    f"🛑 **Invalidación**: `{price*1.006:,.1f}`\n"
                    f"🏁 **Targets**: `{price*0.988:,.1f}` | `{price*0.972:,.1f}`\n"
                )

        # 8. Ensamblado del veredicto
        confirmed_block = "\n".join(confirmed) if confirmed else "Sin confirmaciones institucionales."
        warnings_block  = ("\n⚠️ *Advertencias*:\n" + "\n".join(warnings)) if warnings else ""

        verdict = (
            f"🏛️ *{profile['label']}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"☣️ *VPIN*: `{vpin:.3f}` ✅  |  "
            f"📈 *Régimen*: `{regime}`\n"
            f"📐 *Z-HTF*: `{z_htf:+.2f}`  |  "
            f"📅 *Z-Daily*: `{z_d:+.2f}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"{confirmed_block}\n"
            f"{setup_block}"
            f"{warnings_block}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 *Sizing*: {sizing}"
        )

        return verdict

    def _load_jsons(self, filenames: list) -> Dict:
        data = {}
        for fname in filenames:
            fpath = DATA_DIR / fname
            if fpath.exists():
                try:
                    with open(fpath) as f:
                        data[fname] = json.load(f)
                except: pass
        return data

    def _load_skills(self, filenames: list) -> str:
        all_skills = []
        for filename in filenames:
            fpath = SKILLS_DIR / filename
            if fpath.exists():
                try:
                    all_skills.append(f"--- SKILL: {filename} ---\n{fpath.read_text()[:3000]}")
                except: pass
        return "\n\n".join(all_skills)

    def _get(self, data: dict, keys: list, default):
        for obj in data.values():
            if isinstance(obj, dict):
                for k in keys:
                    if k in obj:
                        return obj[k]
                for v in obj.values():
                    if isinstance(v, dict):
                        for k in keys:
                            if k in v:
                                return v[k]
        return default


# Singleton
_analyst = None
def get_analyst() -> AIAnalyst:
    global _analyst
    if _analyst is None:
        _analyst = AIAnalyst()
    return _analyst
