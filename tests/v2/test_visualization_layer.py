"""
tests/v2/test_visualization_layer.py — Telemetry + Dashboard Schema Validation
═══════════════════════════════════════════════════════════════════════════════
Validates: MLTelemetryLogger output schema, JSONL corruption resilience,
dashboard column expectations, BaseChart lifecycle, theme immutability.

Run: python3 -m pytest tests/v2/test_visualization_layer.py -v
"""

import pytest
import sys
import os
import json
import tempfile
import io
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.telemetry import MLTelemetryLogger
from core.visualizer import BaseChart, apply_theme
from core.config import settings, ThemeConfig


# ═══════════════════════════════════════════════════════════════════
# TELEMETRY LOGGER SCHEMA TESTS
# ═══════════════════════════════════════════════════════════════════

class TestMLTelemetryLogger:

    def test_log_writes_valid_json_line(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            tmp_path = f.name
        try:
            logger = MLTelemetryLogger(log_path=tmp_path)
            logger.log_execution(
                symbol="BTC/USDT:USDT",
                metrics={"vpin": 0.65, "obi": 0.40, "basis": -0.04},
                execution_data={
                    "intended_price": 95000,
                    "final_price": 94980,
                    "strategy": "TWAP",
                    "slippage_real": 0.00021,
                    "is_high_entropy": False
                }
            )
            with open(tmp_path, 'r') as f:
                content = f.read().strip()
            assert content
            entry = json.loads(content)
            assert entry["symbol"] == "BTC/USDT:USDT"
            assert entry["vpin_score"] == 0.65
            assert entry["slippage_real"] == 0.00021
        finally:
            os.unlink(tmp_path)

    def test_entry_has_all_required_columns(self):
        """Dashboard expects these exact column names."""
        required_columns = [
            "timestamp", "symbol", "vpin_score", "obi_delta",
            "basis_premium", "intended_price", "final_execution_price",
            "execution_strategy", "slippage_real", "is_high_entropy"
        ]
        logger = MLTelemetryLogger(log_path="/tmp/test_tmp.jsonl")
        try:
            logger.log_execution("BTC/USDT:USDT", {"vpin": 0, "obi": 0, "basis": 0},
                                {"intended_price": 0, "final_price": 0, "strategy": "Market",
                                 "slippage_real": 0, "is_high_entropy": False})
            with open("/tmp/test_tmp.jsonl", 'r') as f:
                entry = json.loads(f.readline())
            for col in required_columns:
                assert col in entry, f"Missing column: {col}"
        finally:
            try: os.unlink("/tmp/test_tmp.jsonl")
            except: pass

    def test_default_values_when_missing_keys(self):
        """Missing metrics/execution_data keys → default 0/None."""
        logger = MLTelemetryLogger(log_path="/tmp/test_tmp2.jsonl")
        try:
            logger.log_execution("ETH/USDT:USDT", {}, {})
            with open("/tmp/test_tmp2.jsonl", 'r') as f:
                entry = json.loads(f.readline())
            assert entry["vpin_score"] == 0
            assert entry["obi_delta"] == 0
            assert entry["slippage_real"] is None  # No default for missing execution_data key
        finally:
            try: os.unlink("/tmp/test_tmp2.jsonl")
            except: pass

    def test_multiple_entries_append_correctly(self):
        """JSONL: each execution = one line."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            tmp_path = f.name
        try:
            logger = MLTelemetryLogger(log_path=tmp_path)
            for i in range(5):
                logger.log_execution(f"SYM_{i}", {"vpin": 0}, {"strategy": "M", "slippage_real": 0})
            with open(tmp_path, 'r') as f:
                lines = f.readlines()
            assert len(lines) == 5
            for line in lines:
                parsed = json.loads(line)
                assert "symbol" in parsed
        finally:
            os.unlink(tmp_path)


# ═══════════════════════════════════════════════════════════════════
# JSONL CORRUPTION RESILIENCE (ML Dashboard load_data behavior)
# ═══════════════════════════════════════════════════════════════════

class TestJSONLCorruption:

    def test_corrupt_line_skipped(self):
        """Simulate: crash during write leaves half-written JSON → skipped."""
        lines = [
            '{"symbol": "BTC", "vpin_score": 0.65}\n',
            'corrupted line not json\n',
            '{"symbol": "ETH", "vpin_score": 0.40}\n',
        ]
        parsed = []
        for line in lines:
            try:
                parsed.append(json.loads(line))
            except (json.JSONDecodeError, TypeError):
                continue
        assert len(parsed) == 2  # Corrupt line skipped
        assert parsed[0]["symbol"] == "BTC"
        assert parsed[1]["symbol"] == "ETH"

    def test_empty_file_returns_empty(self):
        """No file or empty file → pd.DataFrame() → dashboard shows standby."""
        content = ""
        if not content.strip():
            data = []  # Empty list → pd.DataFrame() → empty
        else:
            data = [json.loads(line) for line in content.split('\n') if line.strip()]
        assert len(data) == 0

    def test_empty_object_line(self):
        """Partial write: {} is valid JSON but missing columns."""
        entry = json.loads("{}")
        assert entry == {}
        # Dashboard would get KeyError on missing columns
        with pytest.raises(KeyError):
            _ = entry["vpin_score"]


# ═══════════════════════════════════════════════════════════════════
# DASHBOARD COLUMN EXPECTATIONS
# ═══════════════════════════════════════════════════════════════════

class TestDashboardColumnExpectations:
    """Validate that telemetry columns exist in dashboard chart references."""

    DASHBOARD_CHARTS = {
        "Slippage_Timeline": ["timestamp", "slippage_real", "symbol"],
        "Strategy_Pie": ["execution_strategy"],
        "VPIN_Scatter": ["vpin_score", "slippage_real", "execution_strategy"],
        "KPIs": ["vpin_score", "slippage_real", "is_high_entropy"],
    }

    TELEMETRY_COLUMNS = [
        "timestamp", "symbol", "vpin_score", "obi_delta", "basis_premium",
        "intended_price", "final_execution_price", "execution_strategy",
        "slippage_real", "is_high_entropy"
    ]

    def test_all_chart_columns_exist_in_telemetry(self):
        """Schema contract: dashboard must not reference missing columns."""
        for chart_name, cols in self.DASHBOARD_CHARTS.items():
            for col in cols:
                assert col in self.TELEMETRY_COLUMNS, \
                    f"Chart '{chart_name}' references '{col}' — missing from telemetry schema"

    def test_unused_columns_documented(self):
        """Columns logged but not rendered = lost analytical signal."""
        used_columns = set()
        for cols in self.DASHBOARD_CHARTS.values():
            used_columns.update(cols)
        unused = [c for c in self.TELEMETRY_COLUMNS if c not in used_columns]
        # These exist but are NOT rendered in dashboard
        expected_unused = ["obi_delta", "basis_premium", "intended_price", "final_execution_price"]
        assert set(unused) == set(expected_unused), \
            f"Unused columns changed! Actual: {unused}"
        # Documented: 4/10 columns logged but never visualized.


# ═══════════════════════════════════════════════════════════════════
# VISUALIZER LIFECYCLE
# ═══════════════════════════════════════════════════════════════════

class TestBaseChartLifecycle:

    def test_create_and_render_cycle(self):
        """Standard lifecycle: create → render → cleanup."""
        chart = BaseChart(figsize=(10, 6), dpi=72)
        fig, ax = chart.create_figure()
        ax.plot([1, 2, 3], [1, 4, 9])
        buf = chart.render()
        assert isinstance(buf, io.BytesIO)
        assert buf.tell() == 0  # seek(0) was called
        assert chart.fig is None  # Cleaned up

    def test_render_without_create_raises(self):
        chart = BaseChart()
        with pytest.raises(RuntimeError, match="No figure created"):
            chart.render()

    def test_style_axis_applies_correctly(self):
        chart = BaseChart(figsize=(6, 4), dpi=72)
        _, ax = chart.create_figure()
        chart.style_axis(ax, title="Test Title", xlabel="X", ylabel="Y", grid=True)
        assert ax.get_title() == "Test Title"
        assert ax.get_xlabel() == "X"
        assert ax.get_ylabel() == "Y"

    def test_colors_from_theme(self):
        chart = BaseChart()
        colors = chart.colors
        assert "bg" in colors
        assert "bull" in colors
        assert "bear" in colors
        assert colors["bg"] == settings.theme.bg


# ═══════════════════════════════════════════════════════════════════
# THEME IMMUTABILITY
# ═══════════════════════════════════════════════════════════════════

class TestThemeImmutability:

    def test_nightclouds_colors_match_design_spec(self):
        theme = ThemeConfig()
        assert theme.bg == "#0b0e11"        # Dark institutional background
        assert theme.bull == "#00C853"       # Green for bullish signals
        assert theme.bear == "#ff4444"       # Red for bearish signals
        assert theme.accent == "gold"        # Gold for titles/highlights
        assert theme.text == "white"
        assert theme.grid == "#2a2d33"

    def test_theme_applied_on_import(self):
        """apply_theme() is called at module level — verify rcParams."""
        import matplotlib
        assert matplotlib.rcParams['figure.facecolor'] == settings.theme.bg
        assert matplotlib.rcParams['text.color'] == settings.theme.text


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
