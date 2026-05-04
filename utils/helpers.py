"""
utils/helpers.py — Shared Utilities for ccxtv2
═══════════════════════════════════════════════════════════════════════════
Consolidates orphan utility functions identified by the structural audit.
"""

import json
import logging
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional
import ccxt.async_support as ccxt

class Session(str, Enum):
    LONDON = "LONDON"
    NEW_YORK = "NEW_YORK"
    OVERLAP = "LONDON_NY_OVERLAP"
    OFF_HOURS = "OFF_HOURS"

def load_json_safe(file_path: str) -> Dict[str, Any]:
    """Safely loads a JSON file, handling double-encoding and corruption."""
    path = Path(file_path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        # Handle double-encoded strings from Action Server results
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                pass
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, IOError):
        return {}

def audit_log(message: str, level: str = "INFO", component: str = "SYSTEM") -> None:
    """Standardized institutional audit logging."""
    timestamp = datetime.now(timezone.utc).isoformat()
    log_line = f"{timestamp} [{component}] {level}: {message}"
    print(log_line)
    # Optional: persistent audit log
    audit_file = Path("/home/wek/Escritorio/ccxtv2/data/institutional_audit.log")
    try:
        with open(audit_file, "a") as f:
            f.write(log_line + "\n")
    except IOError:
        pass

def get_current_session() -> Session:
    """Institutional session classification (UTC)."""
    hour = datetime.now(timezone.utc).hour
    if 12 <= hour < 16:
        return Session.OVERLAP
    elif 7 <= hour < 16:
        return Session.LONDON
    elif 16 <= hour < 21:
        return Session.NEW_YORK
    return Session.OFF_HOURS

def calculate_institutional_score(
    tox_idx: float, 
    obi: float, 
    iceberg: float, 
    cvd: float, 
    basis: float
) -> tuple[int, list[str]]:
    """
    Calculates the canonical CCXTV2 Scalp Score.
    Based on the Senior Audit Orchestrator v1.1 logic.
    
    Returns:
        tuple: (score: int, reasons: list[str])
    """
    score = 0
    reasons = []
    
    if tox_idx > 0.60: 
        score += 3
        reasons.append(f"High Toxicity ({tox_idx:.2f})")
    if abs(obi) > 0.35:
        score += 3
        reasons.append(f"Significant OBI ({obi:.2f})")
    if iceberg > 0.40:
        score += 2
        reasons.append(f"Iceberg Activity ({iceberg:.2f})")
    if (cvd > 0 and obi > 0) or (cvd < 0 and obi < 0):
        score += 2
        reasons.append("CVD/OBI Alignment")
    if (obi > 0 and basis < 0) or (obi < 0 and basis > 0):
        score += 1
        reasons.append("Spot Premium Alignment")
        
    return score, reasons

def rate_to_pct(rate_raw: Any) -> float:
    """Convert raw decimal rate to percentage, rounded to 6 decimals."""
    try:
        return round(float(rate_raw) * 100, 6)
    except (TypeError, ValueError):
        return 0.0

def make_exchange(exchange_id: str, exchange_type: str = "future", timeout: int = 30000) -> ccxt.Exchange:
    """CCXT exchange factory with standard institutional config."""
    exchange_cls = getattr(ccxt, exchange_id)
    return exchange_cls({
        "enableRateLimit": True,
        "timeout": timeout,
        "options": {"defaultType": exchange_type},
    })
