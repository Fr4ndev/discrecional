import logging
import httpx
import json
import os
from typing import Optional, Dict, Any
from core.config import settings, DEEPSEEK_API_KEY

logger = logging.getLogger("ccxtv2.ai_orchestrator")

class AIOrchestrator:
    """
    Orchestrates Ph.D. level market analysis using LLMs (DeepSeek / OpenAI).
    
    It bridges the gap between raw quantitative data and qualitative reasoning
    by injecting Ph.D. skills (.md) as institutional context.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "deepseek-chat"):
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.base_url = "https://api.deepseek.com/v1" # Or any OpenAI-compatible endpoint
        self.model = model
        
    @property
    def is_enabled(self) -> bool:
        return bool(self.api_key)

    async def analyze_market(self, 
                             profile_label: str, 
                             data: Dict[str, Any], 
                             skill_content: str) -> str:
        """
        Calls the LLM to perform a Ph.D. level synthesis.
        """
        if not self.is_enabled:
            return "⚠️ AI Orchestrator disabled (Missing API Key)."

        system_prompt = (
            "You are a Ph.D. Institutional Analyst at a Tier-1 HFT Desk. "
            "Your task is to synthesize raw quantitative market data and provide a high-conviction verdict. "
            "You MUST strictly follow the provided institutional skills and thresholds. "
            "Tone: Professional, direct, concise, zero fluff. "
            "Output format: Markdown with clear sections (Dossier, Metrics, Verdict, Sizing)."
        )

        user_content = (
            f"### PROFILE: {profile_label}\n\n"
            f"### INSTITUTIONAL SKILL (CONTEXT):\n{skill_content}\n\n"
            f"### RAW MARKET DATA (JSON):\n{json.dumps(data, indent=2)}\n\n"
            "--- \n"
            "Generate the Ph.D. Verdict now."
        )

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 1000
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"AI API Error: {response.text}")
                    return f"❌ AI API Error ({response.status_code}): {response.text[:200]}"

                res_json = response.json()
                return res_json["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"AI Orchestration Exception: {e}")
            return f"❌ Error in AI Orchestration: {str(e)}"

# Singleton
_orchestrator = None
def get_orchestrator() -> AIOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AIOrchestrator()
    return _orchestrator
