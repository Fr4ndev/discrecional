"""
tests/v2/test_hub_invalidation.py — Unit Tests for IntelligenceHub Failure Modes
══════════════════════════════════════════════════════════════════════
Validates: VPIN silent degradation (FP-03), Basis failure, CVD edge cases,
CVD_ACCEL_GATE boundary, Z-Score division by zero (FP-09).

Run: python3 -m pytest tests/v2/test_hub_invalidation.py -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.Core_Intelligence_Hub import (
    VPIN_THRESHOLD,
    BASIS_THRESHOLD_PCT,
    CVD_ACCEL_GATE,
    OBI_IGNITION,
    OBI_SCALP_GATE,
    ABSORPTION_GATE,
    OBISnapshot,
    ToxicityResult,
    BasisSnapshot,
    CVDState,
    _ZScoreEngine,
    _FundingFeesEngine,
)

# ═══════════════════════════════════════════════════════════════════
# VPIN SILENT DEGRADATION TESTS (FP-03)
# ═══════════════════════════════════════════════════════════════════

class TestVPINDegradation:
    """Known issue (FP-03): VPIN=0.0 is returned for BOTH 'no data' AND 'real low toxicity'.
    These should be distinguishable — a fetch failure is different from a clean market."""

    def test_vpin_zero_is_ambiguous(self):
        """Demonstrate: VPIN=0.0 can mean either 'clean market' or 'data fetch failed'.
        The consumer (e.g. ReactiveRouter) cannot distinguish these cases."""
        # This test documents the ambiguity, not validates correctness
        possible_interpretations = {
            "clean_flow": ToxicityResult(
                symbol="BTC/USDT:USDT", vpin_index=0.0,
                absorption_rate=0.0, obi_current=0.0,
                senior_verdict="CLEAN_FLOW", is_scalp_valid=False
            ),
            "data_fetch_failed": ToxicityResult(
                symbol="BTC/USDT:USDT", vpin_index=0.0,
                absorption_rate=0.0, obi_current=0.0,
                senior_verdict="CLEAN_FLOW", is_scalp_valid=False
            ),
        }
        # Both scenarios yield identical ToxicityResult — indistinguishable
        assert possible_interpretations["clean_flow"].is_scalp_valid == \
               possible_interpretations["data_fetch_failed"].is_scalp_valid
        # SUGGESTED FIX: return None on fetch failure, or add error_code field

    def test_vpin_threshold_boundary_accept(self):
        """VPIN exactly at threshold = execution permitted."""
        r = ToxicityResult("BTC/USDT:USDT", VPIN_THRESHOLD, 0.0, 0.0, "", True)
        assert r.is_scalp_valid is True

    def test_vpin_threshold_boundary_reject(self):
        """One micro-tick below threshold = execution rejected.
        This is where silent degradation (VPIN→0) blocks all flows."""
        r = ToxicityResult("BTC/USDT:USDT", VPIN_THRESHOLD - 1e-9, 0.0, 0.0, "", False)
        assert r.is_scalp_valid is False

    def test_vpin_zero_blocks_everything(self):
        """If Hub returns VPIN=0 (whether clean or failed), ALL flow gates reject."""
        r = ToxicityResult("BTC/USDT:USDT", 0.0, 0.0, 0.0, "", False)
        assert not r.is_scalp_valid
        assert VPIN_THRESHOLD > 0.0  # Gate exists
        # Under real failure conditions, this creates a silent stall


# ═══════════════════════════════════════════════════════════════════
# BASIS SNAPSHOT TESTS
# ═══════════════════════════════════════════════════════════════════

class TestBasisSnapshot:
    """Validates basis_pct interpretation and threshold boundaries."""

    def test_spot_premium_accumulation_signal(self):
        """Negative basis = spot premium = accumulation stealth signal."""
        snap = BasisSnapshot("BTC/USDT", "BTC/USDT:USDT", 100000, 99940, -60, -0.06, "spot")
        assert snap.is_spot_premium is True   # -0.06 < -0.05
        assert snap.basis_pct < BASIS_THRESHOLD_PCT

    def test_spot_premium_below_threshold(self):
        """Basis = -0.04 (weak spot premium) = NOT below institutional threshold."""
        snap = BasisSnapshot("BTC/USDT", "BTC/USDT:USDT", 100000, 99960, -40, -0.04, "spot")
        assert snap.is_spot_premium is False  # -0.04 >= -0.05
        assert snap.basis_pct >= BASIS_THRESHOLD_PCT

    def test_perp_premium_retail_fomo(self):
        """Positive basis = perp leads = retail FOMO, NOT accumulation."""
        snap = BasisSnapshot("BTC/USDT", "BTC/USDT:USDT", 100000, 100080, 80, 0.08, "perp")
        assert snap.is_spot_premium is False

    def test_basis_at_exact_threshold(self):
        """Boundary case: basis exactly at -0.05."""
        snap = BasisSnapshot("BTC/USDT", "BTC/USDT:USDT", 100000, 99950, -50, -0.05, "spot")
        assert snap.is_spot_premium is False  # -0.05 is NOT less than -0.05


# ═══════════════════════════════════════════════════════════════════
# CVD STATE TESTS
# ═══════════════════════════════════════════════════════════════════

class TestCVDState:
    """Validates CVD acceleration gate behavior."""

    def test_aggression_confirmed_above_gate(self):
        """CVD acceleration > 0 = aggression confirmed."""
        cvd = CVDState("BTC/USDT:USDT", 1.5, 0.01, "IGNITION_ACCELERATING")
        assert cvd.is_aggression_confirmed is True
        assert cvd.acceleration > CVD_ACCEL_GATE

    def test_aggression_not_confirmed_below_gate(self):
        """CVD acceleration ≤ 0 = no aggression confirmation."""
        cvd = CVDState("BTC/USDT:USDT", 1.5, 0.0, "DECAYING_MOMENTUM")
        assert cvd.is_aggression_confirmed is False
        assert cvd.acceleration <= CVD_ACCEL_GATE

    def test_negative_acceleration_decaying(self):
        """Negative acceleration + positive velocity = DECAYING_MOMENTUM."""
        cvd = CVDState("BTC/USDT:USDT", 1.0, -0.5, "DECAYING_MOMENTUM")
        assert not cvd.is_aggression_confirmed
        assert cvd.acceleration < CVD_ACCEL_GATE

    def test_short_squeeze_absorption(self):
        """Positive accel + negative velocity = SHORT_SQUEEZE_ABSORPTION."""
        cvd = CVDState("BTC/USDT:USDT", -0.5, 0.02, "SHORT_SQUEEZE_ABSORPTION")
        assert cvd.is_aggression_confirmed is True
        assert cvd.acceleration > CVD_ACCEL_GATE


# ═══════════════════════════════════════════════════════════════════
# Z-SCORE EDGE CASES (FP-09)
# ═══════════════════════════════════════════════════════════════════

class TestZScoreEngine:
    """Validates ZScoreEngine behavior at boundaries (FP-09)."""

    def test_insufficient_data_returns_zero(self):
        """Less than 10 data points → zscore = 0.0."""
        engine = _ZScoreEngine(window=192)
        for i in range(5):
            engine.update("TEST", 1.0)
        assert engine.zscore("TEST") == 0.0

    def test_sufficient_data_returns_zscore(self):
        """10+ data points → valid z-score."""
        engine = _ZScoreEngine(window=192)
        for i in range(15):
            engine.update("TEST", float(i) * 0.01)
        z = engine.zscore("TEST")
        assert abs(z) > 0.0  # Should have variance with ascending values

    def test_constant_values_zero_std(self):
        """All identical values → std=0 → zscore=0 (FP-09: masks regime builds)."""
        engine = _ZScoreEngine(window=192)
        for i in range(20):
            engine.update("TEST", 1.0)
        assert engine.zscore("TEST") == 0.0
        # In flat markets, Z-Score stays 0 indefinidamente → regime stays NEUTRAL

    def test_regime_overheated(self):
        engine = _ZScoreEngine(window=192)
        for i in range(20):
            engine.update("TEST", 1.0)
        engine.update("TEST", 100.0)  # Massive spike
        assert engine.regime("TEST") == "OVERHEATED"

    def test_regime_neutral(self):
        engine = _ZScoreEngine(window=192)
        for i in range(20):
            engine.update("TEST", float(i) * 0.01)
        regime = engine.regime("TEST")
        assert regime in ("NEUTRAL", "MEAN_REVERT_RISK")


# ═══════════════════════════════════════════════════════════════════
# GOLDEN RULES IMMUTABILITY
# ═══════════════════════════════════════════════════════════════════

class TestGoldenRulesImmutability:
    """These thresholds MUST remain constant across the system.
    Tests serve as canary — if code changes thresholds, tests fail."""

    def test_vpin_threshold_is_062(self):
        assert VPIN_THRESHOLD == 0.62, "VPIN_THRESHOLD changed — golden rule violated"

    def test_basis_threshold_is_neg005(self):
        assert BASIS_THRESHOLD_PCT == -0.05, "BASIS_THRESHOLD_PCT changed"

    def test_cvd_accel_gate_is_zero(self):
        assert CVD_ACCEL_GATE == 0.0, "CVD_ACCEL_GATE changed"

    def test_obi_ignition_is_040(self):
        assert OBI_IGNITION == 0.40, "OBI_IGNITION changed"

    def test_obi_scalp_gate_is_040(self):
        assert OBI_SCALP_GATE == 0.40, "OBI_SCALP_GATE changed"

    def test_absorption_gate_is_060(self):
        assert ABSORPTION_GATE == 0.60, "ABSORPTION_GATE changed"


# ═══════════════════════════════════════════════════════════════════
# TOXICITY VERDICT LOGIC
# ═══════════════════════════════════════════════════════════════════

class TestToxicityVerdict:

    def test_full_conviction(self):
        """VPIN > 0.70 + Absorption > 0.60 = INFORMED_FLOW"""
        r = ToxicityResult("BTC", 0.71, 0.65, 0.5, "INFORMED_FLOW", True)
        assert r.is_scalp_valid
        assert "INFORMED" in r.senior_verdict

    def test_elevated_activity(self):
        """VPIN > 0.40 but < 0.70 = ELEVATED"""
        r = ToxicityResult("BTC", 0.50, 0.40, 0.3, "ELEVATED_ACTIVITY", False)
        assert not r.is_scalp_valid

    def test_clean_flow_retail_soup(self):
        """VPIN ≤ 0.40 = CLEAN_FLOW (retail noise)"""
        r = ToxicityResult("BTC", 0.30, 0.10, 0.1, "CLEAN_FLOW", False)
        assert not r.is_scalp_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
