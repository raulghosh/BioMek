"""Equipment models: traditional cable handle vs BioMek forearm device."""

from .anatomy import load_config, SEGMENTS

_cfg = load_config()
_dev = _cfg["device"]

DEVICE_PAD_FROM_WRIST: float = _dev["pad_from_wrist"]
DEVICE_GRIP_FRACTION:  float = _dev["grip_force_fraction"]

FOREARM_LENGTH:    float = SEGMENTS["forearm_length"]
HAND_GRIP_CENTER:  float = SEGMENTS["hand_grip_center"]
UPPER_ARM_LENGTH:  float = SEGMENTS["upper_arm_length"]


class EquipmentModel:
    """Force-application geometry for traditional handle or BioMek device."""

    def __init__(self, mode: str = "traditional"):
        assert mode in ("traditional", "biomek"), f"Unknown mode: {mode}"
        self.mode = mode

    @property
    def label(self) -> str:
        return "Traditional" if self.mode == "traditional" else "BioMek"

    def elbow_force_distance(self) -> float:
        """Distance (m) from elbow joint to cable application point."""
        if self.mode == "traditional":
            return FOREARM_LENGTH + HAND_GRIP_CENTER          # 0.303 m
        return FOREARM_LENGTH - DEVICE_PAD_FROM_WRIST         # 0.233 m

    def shoulder_force_distance(self) -> float:
        """Distance (m) from shoulder joint to cable application point."""
        if self.mode == "traditional":
            return UPPER_ARM_LENGTH + FOREARM_LENGTH + HAND_GRIP_CENTER   # 0.584 m
        return UPPER_ARM_LENGTH + FOREARM_LENGTH - DEVICE_PAD_FROM_WRIST  # 0.514 m

    def grip_fraction(self) -> float:
        """Fraction of cable force carried by grip."""
        return 1.0 if self.mode == "traditional" else DEVICE_GRIP_FRACTION

    def wrist_torque(self, f_cable: float) -> float:
        """Torque (N·m) at the wrist from the cable load."""
        return f_cable * HAND_GRIP_CENTER if self.mode == "traditional" else 0.0
