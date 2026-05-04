import requests
import json
import os
import time
from datetime import datetime

# ── CONFIGURATION ──────────────────────────────────────────────
BASE_URL = "http://localhost:8080/api/actions/funding-action-server"
# API_KEY removed - Running in LOCAL mode without authentication
HEADERS = {
    "Content-Type": "application/json"
}
REPORTS_DIR = "reports_history"
DATA_DIR = "data/audit_runs"
ASSETS = ["BTC", "ETH"]
ALPHA_ASSETS = ["BTC", "ETH", "SOL", "HYPE"]

os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

import sys
sys.path.insert(0, "/home/wek/Escritorio/ccxtv2")
from utils.helpers import calculate_institutional_score

# PATCH-02: Restored class body — __init__, call_action, execute_all_flows (Cycle 5)
# ── CONFIGURATION (deduplicated) ──────────────────────────────
# BASE_URL already defined above at line 8
# ... existing config preserved ...

class SeniorAuditOrchestrator:
    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = os.path.join(DATA_DIR, f"server_audit_{self.timestamp}")
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
                print(f"[Orchestrator] HTTP {resp.status_code} on {endpoint}")
                return None
        except requests.Timeout:
            print(f"[Orchestrator] Timeout: {endpoint}")
            return None
        except Exception as e:
            print(f"[Orchestrator] Error: {endpoint}: {e}")
            return None

    def execute_all_flows(self):
        for asset in ASSETS:
            self.results[f"scalp_tox_{asset}"] = self.call_action(
                "get-toxicity-index",
                {"symbol": f"{asset}/USDT:USDT", "ob_depth": 20, "trade_limit": 500}
            )
            self.results[f"scalp_audit_{asset}"] = self.call_action(
                "microstructure-audit",
                {"symbol": f"{asset}/USDT:USDT"}
            )
        for asset in ASSETS:
            self.results[f"intraday_basis_{asset}"] = self.call_action(
                "get-basis",
                {"symbol_spot": f"{asset}/USDT", "symbol_perp": f"{asset}/USDT:USDT"}
            )
        self.results["intraday_udc"] = self.call_action(
            "get-ultra-deep-confluence",
            {"assets": ",".join(ASSETS), "depth": 100}
        )
        self.results["sfp_triggers"] = self.call_action(
            "detect-confluence-trigger",
            {"assets": ",".join(ALPHA_ASSETS)}
        )
        self.results["ele_potential"] = self.call_action(
            "eth-ele-audit",
            {"symbol": "ETH/USDT:USDT"}
        )
        print(f"[Orchestrator] Captured {len(self.results)} flows.")
        return True

    def calculate_scalp_score(self, asset):
        tox = self.results.get(f"scalp_tox_{asset}")
        audit = self.results.get(f"scalp_audit_{asset}")
        basis_data = self.results.get(f"intraday_basis_{asset}")
        
        if not tox or not audit or not basis_data: return 0, "DATA_MISSING"
        
        try:
            tox_idx = tox.get("toxicity", {}).get("index", 0)
            iceberg = tox.get("iceberg", {}).get("score", 0)
            
            micro = audit.get("microstructure", {})
            obi = micro.get("obi_20", 0)
            cvd = micro.get("cvd_100_trades_usd", 0)
            basis = basis_data.get("basis_pct", 0)
            
            score, reasons = calculate_institutional_score(tox_idx, obi, iceberg, cvd, basis)
            return score, ", ".join(reasons)
        except Exception as e:
            return 0, f"ERROR: {e}"

    def generate_report(self):
        report_path = os.path.join(REPORTS_DIR, f"Institutional_Audit_{self.timestamp}.md")
        report_content = ""
        
        report_content += f"# 🕵️ Senior Desk Institutional Audit — {self.timestamp}\n\n"
        report_content += f"**Market Condition:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CEST\n"
        report_content += f"**Orchestrator:** Antigravity Senior Agent (V1.1)\n\n"
        
        report_content += "## 🏛️ 1. Global Confluence Summary\n\n"
        report_content += "| Asset | Scalp Score | Intraday Bias | Swing Trigger | Verdict |\n"
        report_content += "| :--- | :--- | :--- | :--- | :--- |\n"
        
        for asset in ASSETS:
            score, reasons = self.calculate_scalp_score(asset)
            
            # Intraday Bias
            basis_data = self.results.get(f"intraday_basis_{asset}")
            basis_val = basis_data.get("basis_pct", 0) if isinstance(basis_data, dict) else 0
            intraday_bias = "LONG" if basis_val < -0.03 else "SHORT" if basis_val > 0.05 else "NEUTRAL"
            
            # Swing Trigger
            swing_data = self.results.get("swing_snapshot")
            swing = {}
            if isinstance(swing_data, dict):
                swing = swing_data.get("triggers", {}).get(asset, {})
            swing_trig = "ACTIVE" if swing.get("trigger_conservative") else "NONE"
            
            # Final Verdict
            if score >= 7: final_v = "✅ GO FULL"
            elif score >= 5: final_v = "🟡 GO PARTIAL"
            else: final_v = "❌ NO TRADE"
            
            report_content += f"| {asset} | {score} | {intraday_bias} | {swing_trig} | {final_v} |\n"
        
        report_content += "\n---\n\n"
        
        report_content += "## 🔬 2. Deep Microstructure Analysis\n\n"
        for asset in ASSETS:
            score, reasons = self.calculate_scalp_score(asset)
            report_content += f"### 📍 {asset} Detail\n"
            report_content += f"- **Scalp Score:** {score}/11\n"
            report_content += f"- **Alpha Reasons:** {reasons}\n"
            
            tox_data = self.results.get(f"scalp_tox_{asset}")
            whales = 0
            if isinstance(tox_data, dict):
                whales = tox_data.get("flow_decomposition", {}).get("whale_pct", 0)
            report_content += f"- **Whale Involvement:** {whales}%\n"
            
            udc_data = self.results.get("intraday_udc", {}).get(asset, {})
            udc_summary = udc_data.get("summary", {}) if isinstance(udc_data, dict) else {}
            report_content += f"- **UDC Verdict:** {udc_summary.get('verdict', 'N/A')} ({udc_summary.get('confidence_score', 0)}% confidence)\n\n"

        report_content += "## 🔥 3. Specialized Triggers (ELE & Alpha)\n\n"
        ele_data = self.results.get("ele_potential")
        ele = ele_data if isinstance(ele_data, dict) else {}
        report_content += f"### 🛁 ETH ELE Transition\n"
        report_content += f"- **Verdict:** {ele.get('verdict', 'N/A')}\n"
        report_content += f"- **Potential:** {ele.get('transition_potential', 'N/A')}\n\n"
        
        sfp_data = self.results.get("sfp_triggers")
        sfp = sfp_data if isinstance(sfp_data, dict) else {}
        report_content += f"### 🏹 SFP Triggers\n"
        report_content += f"- **Any Signal:** {sfp.get('any_signal', False)}\n"
        active = sfp.get("active_triggers", {})
        if active:
            report_content += f"- **Active:** {json.dumps(active)}\n"
        else:
            report_content += f"- **Status:** No SFPs active in tracked assets.\n\n"

        report_content += "---\n"
        report_content += "*Generated by CCXTV2 Senior Orchestrator script. Audit files saved in " + self.run_dir + "*"

        with open(report_path, 'w') as f:
            f.write(report_content)

        print(f"✅ Report generated: {report_path}")
        return report_content

if __name__ == "__main__":
    orchestrator = SeniorAuditOrchestrator()
    orchestrator.execute_all_flows()
    report_text = orchestrator.generate_report()
    
    # Print the report to console for immediate visibility
    print("\n" + report_text)
