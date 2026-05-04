#!/usr/bin/env python3
"""
controller.py — Telegram Bot Controller (Senior Analyst Edition)
════━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import asyncio
import logging
import json
import subprocess
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from core.config import settings
from alerts.telegram import TelegramService
from senior_audit_orchestrator import SeniorAuditOrchestrator

# ── Logging ──────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s [CONTROLLER] %(message)s')
logger = logging.getLogger("Controller")

tg = TelegramService()
ALLOWED_CHAT_ID = int(settings.chat_id) if settings.chat_id else None

# ── Senior Tactical Engine ───────────────────────────────────────

class SeniorAnalystEngine:
    """The brain that extracts 'brutal' setups from raw system data."""
    
    DIR = Path("data/snapshots")

    @classmethod
    def _load(cls, f):
        p = cls.DIR / f
        if not p.exists(): return None
        with open(p, 'r') as file: return json.load(file)

    @classmethod
    def analyze_turbo(cls):
        snap = cls._load("turbo_snapshot.json")
        tox = cls._load("turbo_tox_btc.json")
        walls = cls._load("turbo_walls_btc.json")
        zs = cls._load("turbo_zscore.json")
        
        if not snap: return "❌ Fallo en captura de datos Turbo."

        btc = snap.get("BTC", {})
        price = btc.get("price", 0)
        obi = btc.get("obi", 0)
        basis = btc.get("basis", 0)
        
        # Microstructure Depth
        vpin = tox.get("toxicity_index", 0) if tox else 0
        z_val = zs.get("BTC", {}).get("zscore", 0) if zs else 0
        
        # Muro Real Detection
        muro_price = 0
        muro_size = 0
        if walls and "bids" in walls:
            # Find the largest bid wall in the top 10
            top_bids = sorted(walls["bids"], key=lambda x: x[1], reverse=True)[:5]
            if top_bids:
                muro_price, muro_size = top_bids[0]

        # Conviction Logic
        title = "🚀 **DOSSIER DE EJECUCIÓN: BTC TURBO**"
        
        # Determine Bias
        conviction = "NEUTRAL"
        if obi > 0.8 and basis < -0.04 and vpin > 0.6: conviction = "MAX_CONVICTION_LONG"
        elif obi < -0.8 and basis > 0.04 and vpin > 0.6: conviction = "MAX_CONVICTION_SHORT"
        
        metrics = (
            f"📊 **Métricas de Entrada:**\n"
            f"• **Toxicity (VPIN):** {vpin:.4f} ({'Institucional' if vpin>0.62 else 'Retail'})\n"
            f"• **OBI D20:** {obi:+.4f} ({'Carga Pesada' if abs(obi)>0.8 else 'Normal'})\n"
            f"• **Basis:** {basis:+.4f}% ({'Spot Premium' if basis<0 else 'Perp Lead'})\n"
            f"• **Z-Score:** {z_val:+.2f}\n"
        )
        
        if conviction == "MAX_CONVICTION_LONG":
            verdict = "⚔️ **VEREDICTO: LONG AGGRESSIVE (Trap Detected)**"
            setup = (
                f"🎯 **Entrada:** {price:,.1f} - {max(price*0.999, muro_price):,.1f}\n"
                f"🛑 **Stop Loss:** {muro_price*0.998:,.1f} (Bajo muro de {muro_size:.1f} BTC)\n"
                f"🏁 **Targets:** {price*1.008:,.1f} (TP1) | {price*1.018:,.1f} (TP2)\n"
                f"🛡️ **Nota:** Muro real detectado en {muro_price:,.1f}. Spot empujando."
            )
        elif conviction == "MAX_CONVICTION_SHORT":
            verdict = "🏹 **VEREDICTO: SHORT SCALP (Exhaustion)**"
            setup = (
                f"🎯 **Entrada:** {price:,.1f} - {price*1.001:,.1f}\n"
                f"🛑 **Stop Loss:** {price*1.004:,.1f}\n"
                f"🏁 **Targets:** {price*0.992:,.1f} | {price*0.982:,.1f}\n"
            )
        else:
            verdict = "⚖️ **VEREDICTO: ESPERA TÁCTICA**"
            setup = "ℹ️ No hay desequilibrio suficiente para un setup de alta convicción."

        return f"{title}\n\n{metrics}\n{verdict}\n\n{setup}"

    @classmethod
    def analyze_sfp(cls):
        triggers = cls._load("sfp_triggers.json")
        tox = cls._load("sfp_tox_btc.json")
        if not triggers: return "🏹 Sin triggers SFP en HTF Levels."

        asset = "BTC" if "BTC" in triggers else "ETH"
        trig = triggers[asset]
        price = trig.get("trigger_price", 0)
        vpin = tox.get("toxicity_index", 0) if tox else 0
        
        title = f"🏛️ **ALERTA INSTITUCIONAL: SFP {trig['side']}**"
        context = (
            f"📍 **Nivel:** {trig['level_name']}\n"
            f"📊 **Confirmación OBI:** {trig['obi_at_trigger']:+.2f}\n"
            f"🌊 **Toxicity:** {vpin:.2f}\n"
        )
        
        verdict = "🔥 **PLAN DE ACCIÓN: REVERSIÓN INMEDIATA**"
        if trig['side'] == "SHORT":
            setup = (
                f"🎯 **Entry:** Market Sell @ {price:,.1f}\n"
                f"🛑 **Invalidación:** {price*1.003:,.1f} (Cierre M5 sobre High)\n"
                f"🏁 **Target:** {price*0.988:,.1f} (Liquidity Void)\n"
            )
        else:
            setup = (
                f"🎯 **Entry:** Market Buy @ {price:,.1f}\n"
                f"🛑 **Invalidación:** {price*0.997:,.1f}\n"
                f"🏁 **Target:** {price*1.012:,.1f}\n"
            )

        return f"{title}\n\n{context}\n{verdict}\n\n{setup}"

# ── Routine Bridge ────────────────────────────────────────────────

def _get_controller_logger():
    import logging
    for name in ["controller", "ccxtv2.controller", __name__]:
        existing = logging.getLogger(name)
        if existing.handlers:
            return existing
    return logging.getLogger("ccxtv2.routine_bridge")

from core.Core_Intelligence_Hub import VPIN_THRESHOLD, OBI_IGNITION as OBI_THRESHOLD, BASIS_THRESHOLD_PCT as BASIS_THRESHOLD

class RoutineBridge:
    """
    Ejecuta bash scripts de rutinas, parsea los JSON resultantes y
    produce un Veredicto PhD usando las Golden Rules.
    Gestiona el ciclo de vida del Action Server On-Demand.
    """
    
    DATA_DIR   = Path("data")
    REPORTS_DIR = Path("reports_history")
    SCRIPTS    = {
        "omega": "scripts/ignite_omega.sh",
        "turbo": "scripts/ops/run_flows.sh",
        "sfp": "scripts/routines/run_sfp_routine.sh",
        "scalp": "scripts/routines/run_scalp_workflow.sh",
        "intraday": "scripts/routines/run_intraday_workflow.sh",
        "swing": "scripts/ops/run_flows.sh",
        "alpha": "scripts/ops/run_flows.sh",
        "ignition": "scripts/ops/run_flows.sh",
        "decision_matrix": "scripts/ops/run_flows.sh",
        "ele_audit": "scripts/routines/run_ele_routine.sh",
        "full_audit": "scripts/routines/run_full_audit.sh",
    }

    def __init__(self, skills_dir: str = "skills"):
        self._skills_dir = Path(skills_dir)
        self._logger = _get_controller_logger()
        self.REPORTS_DIR.mkdir(exist_ok=True)
        self._server_proc = None
    
    async def _start_server(self) -> bool:
        """Inicia el Action Server en el puerto 8080."""
        self._logger.info("🚀 Iniciando Action Server On-Demand...")
        try:
            # Intentar limpiar puerto 8080 si está ocupado (silenciosamente)
            subprocess.run("fuser -k 8080/tcp", shell=True, capture_output=True)
            await asyncio.sleep(1) # Dar tiempo para liberar el socket
            self._server_proc = await asyncio.create_subprocess_exec(
                "action-server", "start", "--port", "8080", "--dir", "funding_action_server",
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            
            # Polling para asegurar que está listo
            import httpx
            for i in range(15):
                await asyncio.sleep(2)
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.get("http://localhost:8080/openapi.json", timeout=2)
                        if resp.status_code == 200:
                            self._logger.info("✅ Action Server listo.")
                            return True
                except:
                    pass
            return False
        except Exception as e:
            self._logger.error(f"Error iniciando server: {e}")
            return False

    async def _stop_server(self):
        """Detiene el Action Server."""
        if self._server_proc:
            self._logger.info("🛑 Deteniendo Action Server...")
            try:
                self._server_proc.terminate()
                await self._server_proc.wait()
            except:
                pass
            self._server_proc = None

    def _document_report(self, routine: str, verdict: str):
        """Guarda el análisis en reports_history."""
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"analisis_{routine}_{ts}.md"
        path = self.REPORTS_DIR / filename
        
        content = (
            f"# PhD Analysis Report: {routine.upper()}\n"
            f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"{verdict}\n\n"
            f"--- \n*Generated by CCXTV2 Senior Analyst On-Demand*"
        )
        with open(path, "w") as f:
            f.write(content)
        self._logger.info(f"📄 Reporte guardado en {path}")

    async def run_routine(self, routine: str, update=Update, context=ContextTypes.DEFAULT_TYPE, use_ai: bool = False) -> str:
        # Especial logic for auto_senior_analyst.py based routines
        mode_map = {
            "omega": "omega", "full": "full", "full_audit": "full", "alpha": "sfp", "sfp": "sfp",
            "scalp": "scalp", "intraday": "intraday", "swing": "swing",
            "turbo": "intraday", "ignition": "scalp", "ele_audit": "sfp",
            "decision_matrix": "full"
        }
        mode = mode_map.get(routine.lower())
        
        if mode:
            self._logger.info(f"🧬 [AUTO SENIOR] Executing deepseek analysis: {mode}")
            try:
                # Use absolute path to be sure
                script_path = os.path.join(os.getcwd(), "auto_senior_analyst.py")
                proc = await asyncio.create_subprocess_exec(
                    "python3", script_path, "--mode", mode,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                out = stdout.decode('utf-8')
                
                # Extract from stdout (everything printed by auto_senior_analyst)
                verdict = ""
                delimiter = "=" * 60
                if delimiter in out:
                    parts = out.split(delimiter)
                    if len(parts) >= 3:
                        verdict = parts[-2].strip()
                
                if not verdict:
                    # Fallback to finding the newest file in reports_history
                    import glob
                    reports = glob.glob(str(self.REPORTS_DIR / f"Dossier_{mode.upper()}_*.md"))
                    if reports:
                        latest_report = max(reports, key=os.path.getctime)
                        with open(latest_report, 'r') as f:
                            verdict = f.read()
                
                if not verdict and out.strip():
                    verdict = out.strip()

                if not verdict:
                    return "❌ Error: El analista no generó ningún veredicto legible."

                return verdict
            except Exception as e:
                self._logger.error(f"Auto Senior execution failed: {e}")
                return f"❌ Auto Senior Error: {e}"

        if not script or not Path(script).exists():
            return f"⚠️ Script `{script}` no encontrado. Verifica la ruta."
        
        # 1. Start Server
        server_ready = await self._start_server()
        if not server_ready:
            return "❌ No se pudo iniciar el Action Server. Abortando rutina."

        try:
            # 2. Run Script
            self._logger.info(f"🏃 Ejecutando routine: {routine}")
            cmd = ["bash", script]
            if "run_flows.sh" in script:
                cmd.append(routine)

            proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                self._logger.error(f"[RoutineBridge] {script} stderr: {stderr.decode()[:500]}")
                await self._stop_server()
                return f"❌ Rutina `{routine}` terminó con error:\n```{stderr.decode()[:300]}```"
        except Exception as e:
            self._logger.error(f"Error en run_routine: {e}")
            await self._stop_server()
            return f"❌ Error ejecutando `{routine}`: {e}"
        
        # 3. Stop Server
        await self._stop_server()

        # 4. Build verdict
        from core.ai_analyst import get_analyst
        verdict = await get_analyst().analyze(routine, use_ai=use_ai)
        
        # 5. Document
        self._document_report(routine, verdict)
        
        return verdict

# ── Handlers ──────────────────────────────────────────────────────

async def cmd_start(u, c):
    msg = (
        "🤖 **CCXTV2 Senior Analyst**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🏎️ /turbo | /sfp | /scalp\n"
        "🎯 /intraday | 📅 /swing\n"
        "🛰️ /alpha | 🧬 /omega\n"
        "⚡ /ignition | 🧪 /ele_audit\n"
        "📉 /decision_matrix\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 Usa `ai` después del comando para auditoría profunda.\n"
        "Ej: `/omega ai`"
    )
    await u.message.reply_text(msg, parse_mode="Markdown")

async def cmd_flow_generic(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Handler único para todos los flows."""
    if not u.message or not u.message.text: return
    
    # Check authorization
    if ALLOWED_CHAT_ID and u.message.chat_id != ALLOWED_CHAT_ID:
        logger.warning(f"Unauthorized access attempt from {u.message.chat_id}")
        return

    # Parse command (handle /cmd@botname)
    raw_cmd = u.message.text.split()[0][1:]
    command = raw_cmd.split('@')[0].lower()
    
    args = c.args if c.args else []
    use_ai = "ai" in [a.lower() for a in args]
    
    flow_map = {
        "turbo": "turbo", "sfp": "sfp", "scalp": "scalp",
        "intraday": "intraday", "swing": "swing", "alpha": "alpha", 
        "omega": "omega", "ignition": "ignition", 
        "ele_audit": "ele_audit", "decision_matrix": "decision_matrix",
        "full_audit": "full_audit"
    }
    
    routine = flow_map.get(command)
    if not routine: 
        logger.warning(f"Command '{command}' not recognized in flow_map")
        return

    await u.message.reply_text(f"🚀 Iniciando Análisis On-Demand: *{routine.upper()}* {'(AI Audit)' if use_ai else ''}...", parse_mode="Markdown")
    verdict = await bridge.run_routine(routine, use_ai=use_ai)
    
    # Send in chunks to avoid Telegram 4096 limit
    if len(verdict) > 4000:
        logger.info(f"Sending long report ({len(verdict)} chars) in chunks...")
        chunks = [verdict[i:i+4000] for i in range(0, len(verdict), 4000)]
        for i, chunk in enumerate(chunks):
            try:
                # Add "Part X/Y" for clarity
                header = f"📄 **[PARTE {i+1}/{len(chunks)}]**\n\n" if len(chunks) > 1 else ""
                await u.message.reply_text(header + chunk)
                await asyncio.sleep(0.5) # Avoid flood limits
            except Exception as e:
                logger.error(f"Error sending chunk {i}: {e}")
                # Fallback to plain text if MD fails
                await u.message.reply_text(f"--- Chunk {i+1} Fallback ---\n" + chunk)
    else:
        # Try Markdown first, fallback to plain if it fails
        try:
            await u.message.reply_text(verdict, parse_mode="Markdown")
        except:
            await u.message.reply_text(verdict)

async def cmd_analysis(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Handler genérico: /analysis <perfil> [ai]"""
    from core.ai_analyst import get_analyst
    args = c.args if c.args else []
    profile = args[0].lower() if args else "omega"
    use_ai = "ai" in [a.lower() for a in args]
    
    await u.message.reply_text(
        f"🧠 Analizando perfil *{profile.upper()}* {'(vía DeepSeek PhD)' if use_ai else ''}...",
        parse_mode="Markdown"
    )
    verdict = await get_analyst().analyze(profile, use_ai=use_ai)
    await u.message.reply_text(verdict, parse_mode="Markdown")

async def cmd_status(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """Muestra estado de todos los flows y último trigger del Router."""
    from core.reactive_router import get_router
    import time
    router = get_router()
    lines = ["🏛️ *ESTADO DEL SISTEMA*\n━━━━━━━━━━━━━━━━━━━━━"]
    for flow, last_ts in router._last_run.items():
        ago = int(time.time() - last_ts)
        lines.append(f"• {flow}: hace {ago}s")
    if not router._last_run:
        lines.append("• Sin flows ejecutados aún.")
    await u.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def post_init(application):
    """Setups the bot commands menu in Telegram."""
    from telegram import BotCommand
    commands = [
        BotCommand("start", "Mostrar panel de control"),
        BotCommand("turbo", "Auditoría Triple Capa"),
        BotCommand("sfp", "Reversional"),
        BotCommand("scalp", "Micro-Tendencia"),
        BotCommand("intraday", "Captura de Sesión"),
        BotCommand("swing", "Cambio de Régimen"),
        BotCommand("alpha", "Veredicto Híbrido"),
        BotCommand("omega", "Rutina Integral Integral"),
        BotCommand("ignition", "Market Momentum"),
        BotCommand("ele_audit", "ETH Transition"),
        BotCommand("decision_matrix", "Confluence Audit"),
        BotCommand("full_audit", "Full Institutional Audit"),
        BotCommand("analysis", "Análisis On-Demand"),
        BotCommand("status", "Estado del sistema"),
    ]
    await application.bot.set_my_commands(commands)

def main():
    app = ApplicationBuilder().token(settings.telegram_token).post_init(post_init).build()
    
    global bridge
    bridge = RoutineBridge()
    
    app.add_handler(CommandHandler("start", cmd_start))
    for cmd in ["turbo", "sfp", "scalp", "intraday", "swing", "alpha", "omega", "ignition", "ele_audit", "decision_matrix", "full_audit"]:
        app.add_handler(CommandHandler(cmd, cmd_flow_generic))

    app.add_handler(CommandHandler("analysis", cmd_analysis))
    app.add_handler(CommandHandler("status", cmd_status))
    
    logger.info("Bot started. Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == '__main__':
    main()
