"""Equipment models: traditional cable handle vs BioMek forearm device."""

from .anatomy import SEGMENTS, load_config
from pathlib import Path

_cfg = load_config()
_dev = _cfg["device"]

DEVICE_PAD_FROM_WRIST: float = _dev["pad_from_wrist"]
DEVICE_GRIP_FRACTION: float = _dev["grip_force_fraction"]

FOREARM_LENGTH: float = SEGMENTS["forearm_length"]
HAND_GRIP_CENTER: float = SEGMENTS["hand_grip_center"]
UPPER_ARM_LENGTH: float = SEGMENTS["upper_arm_length"]


class EquipmentModel:
    """Models force application for traditional handle or BioMek device."""

    def __init__(self, mode: str = "traditional"):
        assert mode in ("traditional", "biomek"), f"Unknown mode: {mode}"
        self.mode = mode

    def force_distance_from_elbow(self) -> float:
        """Distance (m) from elbow to the cable force application point."""
        if self.mode == "traditional":
            return FOREARM_LENGTH + HAND_GRIP_CENTER
        return FOREARM_LENGTH - DEVICE_PAD_FROM_WRIST

    def force_distance_from_shoulder(self) -> float:
        """Distance (m) from shoulder to cable force application point."""
        if self.mode == "traditional":
            return UPPER_ARM_LENGTH + FOREARM_LENGTH + HAND_GRIP_CENTER
        return UPPER_ARM_LENGTH + FOREARM_LENGTH - DEVICE_PAD_FROM_WRIST

    def grip_force_fraction(self) -> float:
        """Fraction of cable force borne by grip."""
        return 1.0 if self.mode == "traditional" else DEVICE_GRIP_FRACTION

    def wrist_torque(self, f_cable: float) -> float:
        """Torque (N·m) at the wrist from cable force."""
        if self.mode == "traditional":
            return f_cable * HAND_GRIP_CENTER
        return 0.0
