
import asyncio
import sys
import os

sys.path.insert(0, "/home/wek/Escritorio/ccxtv2")
sys.path.insert(0, "/home/wek/Escritorio/ccxtv2/funding_action_server")

from actions.audit_actions import run_scalp_workflow

try:
    res = run_scalp_workflow(assets="BTC")
    print(res)
except Exception as e:
    import traceback
    traceback.print_exc()
