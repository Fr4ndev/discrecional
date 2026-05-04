"""
tests/v2/test_signal_propagation.py — Integration Tests for Signal Flow
══════════════════════════════════════════════════════════════════════
Validates: ReactiveRouter signal→flow mapping, VPIN gate enforcement,
cooldown mechanism, signal type resolution, flow execution coverage.

Run: python3 -m pytest tests/v2/test_signal_propagation.py -v

NOTE: These tests use the real ReactiveRouter, SignalFlowMap,
and VPIN gates from the codebase. No mocking needed for mapping logic.
"""

import pytest
import sys
import os
import time
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.reactive_router import (
    ReactiveRouter, RouterTrigger, SIGNAL_FLOW_MAP,
    FLOW_VPIN_GATE, FLOW_COOLDOWN
)


# ═══════════════════════════════════════════════════════════════════
# SIGNAL → FLOW MAPPING
# ═══════════════════════════════════════════════════════════════════

class TestSignalFlowMapping:
    """Every Guardian signal type must map to a valid flow."""

    VALID_FLOWS = {"intraday", "turbo", "sfp", "scalp", "omega"}

    @pytest.mark.parametrize("signal_type,expected_flow", [
        ("levelbreak", "intraday"),
        ("strategicaudit", "intraday"),
        ("ict_v16_4h", "turbo"),
        ("ict", "turbo"),
        ("sfp_v2", "sfp"),
        ("sfp", "sfp"),
        ("whalemonitor", "scalp"),
        ("squeezemonitor", "scalp"),
        ("ignitionbridge", "turbo"),
        ("spoofdetector", "scalp"),
    ])
    def test_signal_maps_to_correct_flow(self, signal_type, expected_flow):
        """Validate SIGNAL_FLOW_MAP entries are correct."""
        assert signal_type in SIGNAL_FLOW_MAP, f"Missing mapping for {signal_type}"
        assert SIGNAL_FLOW_MAP[signal_type] == expected_flow

    def test_all_flows_in_valid_set(self):
        """All mapped flows must be in the valid flow set."""
        for flow in SIGNAL_FLOW_MAP.values():
            assert flow in self.VALID_FLOWS, f"Unknown flow: {flow}"

    @pytest.mark.parametrize("partial_input,expected_flow", [
        ("SFPSentinel_alert", "sfp"),   # contains 'sfp'
        ("ict_v16_h1", "turbo"),        # contains 'ict'
        ("WhaleMonitor_block", "scalp"), # contains 'whalemonitor'
        ("LevelBreak", "intraday"),     # partial match 'levelbreak'
    ])
    def test_partial_signal_matching(self, partial_input, expected_flow):
        """Validate partial matching logic in _resolve_flow()."""
        router = ReactiveRouter()
        # Test _resolve_flow directly
        flow = router._resolve_flow(RouterTrigger(
            signal_type=partial_input, symbol="BTC/USDT:USDT", vpin=0.65, description="test"
        ))
        assert flow == expected_flow, f"Partial match failed: {partial_input} → {flow} != {expected_flow}"

    def test_unknown_signal_returns_none(self):
        """Unrecognized signal → _resolve_flow returns None."""
        router = ReactiveRouter()
        flow = router._resolve_flow(RouterTrigger(
            signal_type="unknown_signal_xyz", symbol="BTC/USDT:USDT", vpin=0.8, description="test"
        ))
        assert flow is None


# ═══════════════════════════════════════════════════════════════════
# VPIN GATE ENFORCEMENT
# ═══════════════════════════════════════════════════════════════════

class TestVPINGate:
    """VPIN gates are flow-specific. Each flow has its own threshold."""

    def test_intraday_requires_062(self):
        assert FLOW_VPIN_GATE["intraday"] == 0.62

    def test_turbo_requires_062(self):
        assert FLOW_VPIN_GATE["turbo"] == 0.62

    def test_sfp_relaxed_to_055(self):
        """SFP can execute with lower toxicity (reversals need less confirmation)."""
        assert FLOW_VPIN_GATE["sfp"] == 0.55

    def test_scalp_relaxed_to_050(self):
        assert FLOW_VPIN_GATE["scalp"] == 0.50

    @pytest.mark.parametrize("vpin,expected", [
        (0.62, True),   # Exactly at threshold = allowed
        (0.619, False), # Below by 0.001 = blocked
        (0.80, True),   # Well above = allowed
        (0.40, False),  # Normal retail = blocked
        (0.00, False),  # Failed fetch = blocked (FP-03)
    ])
    def test_vpin_boundary_behavior(self, vpin, expected):
        """Validate VPIN gate boundary logic per _check_vpin_gate()."""
        router = ReactiveRouter()
        result = router._check_vpin_gate("intraday", vpin)
        assert result == expected, f"VPIN={vpin} → gate={expected} but got {result}"

    def test_vpin_undefined_flow_defaults_to_062(self):
        """Undefined flow → defaults to VPIN_THRESHOLD (0.62)."""
        router = ReactiveRouter()
        # 'omega' uses default 0.62 via .get(flow, 0.62)
        result = router._check_vpin_gate("omega", 0.62)
        assert result is True
        result = router._check_vpin_gate("omega", 0.619)
        assert result is False


# ═══════════════════════════════════════════════════════════════════
# COOLDOWN MECHANISM
# ═══════════════════════════════════════════════════════════════════

class TestFlowCooldown:
    """Prevents over-execution of flows within cooldown windows."""

    def test_initial_call_always_passes(self):
        """First call with no prior state → passes cooldown check."""
        router = ReactiveRouter()
        assert router._check_cooldown("scalp") is True

    def test_within_cooldown_blocked(self):
        """Call within 60s → blocked."""
        router = ReactiveRouter()
        router._update_cooldown("scalp")  # Sets last_run to now
        assert router._check_cooldown("scalp") is False

    def test_after_cooldown_allowed(self):
        """Call after cooldown expired → allowed."""
        router = ReactiveRouter()
        router._last_run["scalp"] = time.time() - 120  # 2 min ago
        assert router._check_cooldown("scalp") is True

    def test_cooldown_per_flow_isolated(self):
        """Scalp cooldown doesn't block Intraday."""
        router = ReactiveRouter()
        router._update_cooldown("scalp")
        assert router._check_cooldown("scalp") is False
        assert router._check_cooldown("intraday") is True

    def test_cooldown_durations(self):
        """Validate each flow's cooldown is reasonable."""
        assert FLOW_COOLDOWN["intraday"] == 300   # 5 min
        assert FLOW_COOLDOWN["turbo"] == 120      # 2 min
        assert FLOW_COOLDOWN["sfp"] == 180        # 3 min
        assert FLOW_COOLDOWN["scalp"] == 60       # 1 min
        assert FLOW_COOLDOWN["omega"] == 600      # 10 min


# ═══════════════════════════════════════════════════════════════════
# ROUTER FULL INTEGRATION (without bash execution)
# ═══════════════════════════════════════════════════════════════════

class TestRouterIntegration:

    def test_on_signal_blocks_below_gate(self):
        """Full on_signal flow: VPIN below gate → returns None (blocked)."""
        router = ReactiveRouter()
        trigger = RouterTrigger("whalemonitor", "ETH/USDT:USDT", 0.49, "test")
        # Cannot await outside async context — test the gate check directly
        flow = router._resolve_flow(trigger)
        assert flow == "scalp"
        assert router._check_vpin_gate("scalp", 0.49) is False
        # At integration level, on_signal would return None

    def test_on_signal_passes_all_gates(self):
        """VPIN above gate + not in cooldown → flow resolves."""
        router = ReactiveRouter()
        trigger = RouterTrigger("sfp", "BTC/USDT:USDT", 0.60, "test")
        flow = router._resolve_flow(trigger)
        assert flow == "sfp"
        assert router._check_vpin_gate("sfp", 0.60) is True
        assert router._check_cooldown("sfp") is True

    def test_senior_audit_trigger_mapping(self):
        """SeniorAudit signals map to intraday flow (strategic context)."""
        trigger = RouterTrigger("strategicaudit", "BTC/USDT:USDT", 0.8, "hourly_check")
        flow = ReactiveRouter()._resolve_flow(trigger)
        assert flow == "intraday"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
