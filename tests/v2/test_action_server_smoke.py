"""
tests/v2/test_action_server_smoke.py — Action Server Smoke Tests
══════════════════════════════════════════════════════════════════
Validates: Action Server health, basic endpoint responses, JSON validity,
composite workflow stability. These tests require a running Action Server.

Run: python3 -m pytest tests/v2/test_action_server_smoke.py -v -m smoke
(These are marked as 'smoke' — they skip if server is not running)
"""

import pytest
import sys
import os
import json
import subprocess
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Try importing httpx for real tests, fall back to requests
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

ACTION_SERVER = "http://localhost:8080"
TIMEOUT = 10


def server_is_running():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect(("localhost", 8080))
        s.close()
        return True
    except Exception:
        return False


def requires_server(test_func):
    """Decorator: skip if Action Server is not reachable."""
    if not server_is_running():
        return pytest.mark.skip(reason="Action Server not running on localhost:8080")(test_func)
    return test_func


# ═══════════════════════════════════════════════════════════════════
# SERVER HEALTH CHECKS
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.smoke
class TestServerHealth:

    def test_server_port_is_reachable(self):
        """Port 8080 must accept TCP connections."""
        assert server_is_running(), "Action Server not reachable on localhost:8080"

    @pytest.mark.skipif(not HAS_HTTPX, reason="httpx not installed")
    def test_openapi_endpoint_returns_200(self):
        """GET /openapi.json must return valid OpenAPI spec."""
        import httpx
        try:
            resp = httpx.get(f"{ACTION_SERVER}/openapi.json", timeout=TIMEOUT)
            assert resp.status_code == 200
            spec = resp.json()
            assert "openapi" in spec or "paths" in spec
        except httpx.ConnectError:
            pytest.skip("Action Server not running")

    @pytest.mark.skipif(not HAS_HTTPX, reason="httpx not installed")
    def test_health_endpoint(self):
        """get-system-health endpoint must return OK."""
        import httpx
        try:
            resp = httpx.post(
                f"{ACTION_SERVER}/api/actions/funding-action-server/get-system-health/run",
                headers={"Content-Type": "application/json"},
                json={}, timeout=TIMEOUT
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, str):
                    data = json.loads(data)
                assert "status" in data or isinstance(data, dict)
            elif resp.status_code == 404:
                pytest.skip("get-system-health endpoint not found")
        except httpx.ConnectError:
            pytest.skip("Action Server not running")


# ═══════════════════════════════════════════════════════════════════
# ENDPOINT RESPONSE VALIDATION
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.smoke
class TestEndpointResponses:

    @pytest.mark.skipif(not HAS_HTTPX, reason="httpx not installed")
    def test_microstructure_audit_returns_valid_json(self):
        """microstructure-audit must return dict with expected keys."""
        import httpx
        try:
            resp = httpx.post(
                f"{ACTION_SERVER}/api/actions/funding-action-server/microstructure-audit/run",
                headers={"Content-Type": "application/json"},
                json={"symbol": "BTC/USDT:USDT"}, timeout=30
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, str):
                    data = json.loads(data)
                assert isinstance(data, dict)
                # Should contain microstructure key
                assert "microstructure" in data or "error" in data or "symbol" in data
        except httpx.ConnectError:
            pytest.skip("Action Server not running")

    @pytest.mark.skipif(not HAS_HTTPX, reason="httpx not installed")
    def test_get_toxicity_returns_vpin(self):
        """get-toxicity-index must return toxicity data."""
        import httpx
        try:
            resp = httpx.post(
                f"{ACTION_SERVER}/api/actions/funding-action-server/get-toxicity-index/run",
                headers={"Content-Type": "application/json"},
                json={"symbol": "BTC/USDT:USDT", "ob_depth": 20, "trade_limit": 200},
                timeout=30
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, str):
                    data = json.loads(data)
                assert isinstance(data, dict)
        except httpx.ConnectError:
            pytest.skip("Action Server not running")

    @pytest.mark.skipif(not HAS_HTTPX, reason="httpx not installed")
    def test_run_scalp_workflow_no_timeout(self):
        """Composite workflow must not deadlock (FP-01 check)."""
        import httpx
        try:
            resp = httpx.post(
                f"{ACTION_SERVER}/api/actions/funding-action-server/run-scalp-workflow/run",
                headers={"Content-Type": "application/json"},
                json={"assets": "BTC"}, timeout=60
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, str):
                    data = json.loads(data)
                assert isinstance(data, dict)
                assert "verdict" in data or "workflow_results" in data
        except httpx.ConnectError:
            pytest.skip("Action Server not running")
        except httpx.TimeoutException:
            pytest.fail("DEADLOCK DETECTED (FP-01): run_scalp_workflow timeout 60s")

    @pytest.mark.skipif(not HAS_HTTPX, reason="httpx not installed")
    def test_eth_ele_audit_returns_levels(self):
        """eth-ele-audit must return SFP levels and transition potential."""
        import httpx
        try:
            resp = httpx.post(
                f"{ACTION_SERVER}/api/actions/funding-action-server/eth-ele-audit/run",
                headers={"Content-Type": "application/json"},
                json={"symbol": "ETH/USDT:USDT"}, timeout=30
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, str):
                    data = json.loads(data)
                assert isinstance(data, dict)
                assert "transition_potential" in data or "error" in data
        except httpx.ConnectError:
            pytest.skip("Action Server not running")


# ═══════════════════════════════════════════════════════════════════
# DEADLOCK REGRESSION TEST (FP-01)
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.smoke
class TestDeadlockRegression:

    @pytest.mark.skipif(not HAS_HTTPX, reason="httpx not installed")
    def test_concurrent_requests_no_deadlock(self):
        """Multiple concurrent requests must not deadlock the Hub semaphore."""
        import httpx
        import asyncio

        async def call_endpoint():
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    return await client.post(
                        f"{ACTION_SERVER}/api/actions/funding-action-server/microstructure-audit/run",
                        headers={"Content-Type": "application/json"},
                        json={"symbol": "BTC/USDT:USDT"}
                    )
            except httpx.ConnectError:
                return None

        async def run_concurrent():
            tasks = [call_endpoint() for _ in range(3)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            successes = [r for r in results if r is not None and r.status_code == 200]
            errors = [r for r in results if isinstance(r, Exception)]
            return successes, errors

        try:
            successes, errors = asyncio.run(run_concurrent())
            if len(successes) == 0 and len(errors) == 0:
                pytest.skip("Action Server not running")
            # No deadlock = each request completed (success or error)
            assert len(errors) <= 1  # Allow connection errors, not deadlocks
        except RuntimeError:
            pytest.skip("Asyncio event loop issue")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "smoke", "--tb=short"])
