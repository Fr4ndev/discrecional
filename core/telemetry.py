import json
import os
from datetime import datetime, timezone

class MLTelemetryLogger:
    def __init__(self, log_path="/home/wek/Escritorio/ccxtv2/logs/execution_features.jsonl"):
        self.log_path = log_path
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def log_execution(self, symbol, metrics, execution_data):
        # Flattened object for ML
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "vpin_score": metrics.get("vpin", 0),
            "obi_delta": metrics.get("obi", 0),
            "basis_premium": metrics.get("basis", 0),
            "intended_price": execution_data.get("intended_price"),
            "final_execution_price": execution_data.get("final_price"),
            "execution_strategy": execution_data.get("strategy"), # Fragmented/Single
            "slippage_real": execution_data.get("slippage_real"),
            "is_high_entropy": execution_data.get("is_high_entropy", False)
        }
        
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
            
        print(f"📊 Telemetry logged to {self.log_path}")

# ML Training Schema (JSON)
# {
#   "features": ["vpin_score", "obi_delta", "basis_premium"],
#   "labels": ["slippage_real"],
#   "metadata": ["timestamp", "symbol", "execution_strategy"]
# }
