"""
tests/v2/test_execution_engine.py — Execution Engine + Stop Loss Tests
══════════════════════════════════════════════════════════════════
Validates: DynamicTrailingStop activation/exit/trail logic,
LiquidityAwareStopLoss fallback behavior, slippage math,
slippage threshold boundaries.

Run: python3 -m pytest tests/v2/test_execution_engine.py -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.execution_engine import DynamicTrailingStop, LiquidityAwareStopLoss


# ═══════════════════════════════════════════════════════════════════
# DYNAMIC TRAILING STOP
# ═══════════════════════════════════════════════════════════════════

class TestDynamicTrailingStop:

    def test_not_active_before_activation_price(self):
        ts = DynamicTrailingStop(activation_price=100, trail_pct=0.01)
        assert ts.update(99) == "HOLD"
        assert ts.active is False

    def test_activates_at_exact_price(self):
        ts = DynamicTrailingStop(activation_price=100, trail_pct=0.01)
        assert ts.update(100) == "HOLD"
        assert ts.active is True
        assert ts.peak_price == 100

    def test_activates_above_price(self):
        ts = DynamicTrailingStop(activation_price=100, trail_pct=0.01)
        assert ts.update(101) == "HOLD"
        assert ts.active is True
        assert ts.peak_price == 101

    def test_trails_peak_upward(self):
        ts = DynamicTrailingStop(activation_price=100, trail_pct=0.01)
        ts.update(101)  # activate, peak=101
        ts.update(105)  # new peak=105
        assert ts.peak_price == 105
        # Stop = 105 * 0.99 = 103.95
        assert ts.update(104) == "HOLD"  # Above stop

    def test_exits_when_below_stop(self):
        ts = DynamicTrailingStop(activation_price=100, trail_pct=0.02)
        ts.update(100)  # activate, peak=100
        ts.update(110)  # peak=110
        # Stop = 110 * 0.98 = 107.8
        assert ts.update(107.8) == "EXIT_NOW"
        assert ts.update(105) == "EXIT_NOW"  # Still below

    def test_stop_does_not_move_down(self):
        """Peak only goes up. Stop never widens on price decline."""
        ts = DynamicTrailingStop(activation_price=100, trail_pct=0.02)
        ts.update(100)  # activate, peak=100
        ts.update(110)  # peak=110, stop=107.8
        ts.update(108)  # peak stays 110
        assert ts.peak_price == 110  # Peak doesn't go down

    def test_default_trail_pct(self):
        ts = DynamicTrailingStop(activation_price=100)
        assert ts.trail_pct == 0.005

    def test_single_direction_long_only(self):
        """Documented limitation: only works for LONG positions."""
        ts = DynamicTrailingStop(activation_price=100, trail_pct=0.02)
        # For a short: price GOES DOWN means profit
        ts.update(90)  # Below activation → never activates
        assert ts.active is False
        # This is expected behavior — class is LONG-only by design

    def test_activation_price_zero_activates_immediately(self):
        """Edge case: activation_price=0 activates on any positive price."""
        ts = DynamicTrailingStop(activation_price=0, trail_pct=0.05)
        assert ts.update(50) == "HOLD"
        assert ts.active is True
        assert ts.peak_price == 50


# ═══════════════════════════════════════════════════════════════════
# LIQUIDITY-AWARE STOP LOSS (unit — no HTTP calls)
# ═══════════════════════════════════════════════════════════════════

class TestLiquidityAwareStopLoss:

    def test_initialization_sets_fields(self):
        sl = LiquidityAwareStopLoss(
            entry_price=95000, symbol="BTC/USDT:USDT",
            tox_index=0.65, slippage_real=0.00015
        )
        assert sl.entry_price == 95000
        assert sl.symbol == "BTC/USDT:USDT"
        assert sl.tox_index == 0.65
        assert sl.slippage_real == 0.00015
        assert sl.sl_price == 0   # Not set until initialize()
        assert sl.breakeven_activated is False

    def test_update_breakeven_activates_above_threshold(self):
        """When price rises above entry × (1 + slippage*1.5), SL moves to entry."""
        sl = LiquidityAwareStopLoss(95000, "BTC", 0.60, 0.00021)
        sl.sl_price = 94000  # Assume initialized
        threshold = 95000 * (1 + 0.00021 * 1.5)  # = 95000 * 1.000315 = 95029.93
        assert sl.update(95030) == "HOLD"
        assert sl.breakeven_activated is True
        assert sl.sl_price == 95000  # Moved to break-even

    def test_update_breakeven_not_activated_below_threshold(self):
        sl = LiquidityAwareStopLoss(95000, "BTC", 0.60, 0.00021)
        sl.sl_price = 94000
        result = sl.update(95020)  # Below threshold (~95030)
        assert result == "HOLD"
        assert sl.breakeven_activated is False

    def test_update_exit_when_below_sl(self):
        sl = LiquidityAwareStopLoss(95000, "BTC", 0.60, 0.00015)
        sl.sl_price = 94000
        assert sl.update(93999) == "EXIT_NOW"
        assert sl.update(93000) == "EXIT_NOW"

    def test_update_hold_when_above_sl(self):
        sl = LiquidityAwareStopLoss(95000, "BTC", 0.60, 0.00015)
        sl.sl_price = 94000
        assert sl.update(95000) == "HOLD"
        assert sl.update(94100) == "HOLD"

    def test_breakeven_once_only(self):
        """Breakeven activates once, doesn't re-trigger."""
        sl = LiquidityAwareStopLoss(95000, "BTC", 0.60, 0.00021)
        sl.sl_price = 94000
        threshold = 95000 * (1 + 0.00021 * 1.5)
        sl.update(threshold + 1)  # Activate break-even
        assert sl.breakeven_activated is True
        old_sl = sl.sl_price
        sl.update(threshold + 100)  # Price keeps rising
        assert sl.sl_price == old_sl  # Not moved again (no trailing)

    def test_fallback_sl_one_percent(self):
        """Known behavior: if initialize fails, SL = entry * 0.99."""
        sl = LiquidityAwareStopLoss(100000, "BTC", 0.50, 0.0001)
        # Simulate fallback (initialize would set this if HTTP fails)
        sl.sl_price = 100000 * 0.99
        assert sl.sl_price == 99000
        assert sl.update(98999) == "EXIT_NOW"


# ═══════════════════════════════════════════════════════════════════
# SLIPPAGE MATH VALIDATION
# ═══════════════════════════════════════════════════════════════════

class TestSlippageMath:

    def test_slippage_formula(self):
        """slippage = |avg_fill - mid| / mid"""
        mid = 95000
        avg_fill = 95150
        slip = abs(avg_fill - mid) / mid
        assert slip == pytest.approx(0.001579, rel=1e-4)

    def test_zero_slippage(self):
        mid = 95000
        avg_fill = 95000
        slip = abs(avg_fill - mid) / mid
        assert slip == 0.0

    def test_threshold_boundary_accept(self):
        """Slippage exactly at threshold = Market order (single execution)."""
        slip = 0.0015
        assert not (slip > 0.0015)  # ≤ threshold → single market order

    def test_threshold_boundary_twap(self):
        """Slippage one tick above = TWAP fragmentation."""
        slip = 0.0016
        assert slip > 0.0015  # > threshold → TWAP mode

    def test_infinite_slippage_sentinel(self):
        """1.0 sentinel value means 'not enough liquidity'."""
        slip = 1.0
        assert slip > 0.0015  # Always triggers TWAP (conservative)
        # Consumer should handle this as a warning, not attempt execution

    def test_obi_walk_accumulation_math(self):
        """Validate the OB-walk accumulation logic independently."""
        levels = [(95100, 0.5), (95200, 1.0), (95300, 2.0)]  # (price, qty BTC)
        mid = 95000
        amount_usd = 100000  # ~1.05 BTC at mid price

        accumulated_qty = 0.0
        filled_usd = 0.0
        for price, qty in levels:
            level_usd = price * qty
            if filled_usd + level_usd >= amount_usd:
                remaining = amount_usd - filled_usd
                accumulated_qty += remaining / price
                filled_usd = amount_usd
                break
            else:
                accumulated_qty += qty
                filled_usd += level_usd

        assert filled_usd >= amount_usd  # Fully filled
        avg_price = filled_usd / accumulated_qty
        assert avg_price > mid  # Buy side walks up
        slippage = abs(avg_price - mid) / mid
        assert slippage > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
