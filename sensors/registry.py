from __future__ import annotations

from core.bus import SignalBus
from sensors.base import Sensor
from sensors.legacy_daemon_sensors import (
    IgnitionSensor,
    LevelBreakSensor,
    OpportunitySensor,
    SFPAdvancedSensor,
    ScalpSensor,
    SpoofSensor,
    SqueezeSensor,
    VolumeSensor,
    WhaleSensor,
)


def build_default_sensors(bus: SignalBus) -> list[Sensor]:
    """
    Registers 9 refactored sensors (one per original daemon).
    """
    return [
        WhaleSensor("whale_sentinel", bus, "data/whale_logs.txt"),
        SpoofSensor("spoof_daemon", bus, "data/spoof.log"),
        IgnitionSensor("ignition_daemon", bus, "data/ignition.log"),
        VolumeSensor("volume_daemon", bus, "data/volume.log"),
        ScalpSensor("scalp_daemon", bus, "data/scalp.log"),
        OpportunitySensor("opportunity_sentinel", bus, "data/opportunity_sentinel.log"),
        LevelBreakSensor("level_break_alert", bus, "data/level_break_alert.log"),
        SqueezeSensor("squeeze_watcher", bus, "data/squeeze_watcher.log"),
        SFPAdvancedSensor("sfp_advanced_monitor", bus, "data/sfp_advanced.log"),
    ]
