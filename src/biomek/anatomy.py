"""
Anatomy constants and muscle mechanics helpers.
Loaded from config/simulation.yaml at import time.
"""

import numpy as np
import yaml
from pathlib import Path

_CONFIG_PATH = Path(__file__).parents[2] / "config" / "simulation.yaml"

def load_config(path: Path = _CONFIG_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)

_cfg = load_config()
MUSCLE_PARAMS: dict = _cfg["anatomy"]["muscles"]
JOINT_REF_AREA: dict = _cfg["anatomy"]["joint_ref_areas"]
SEGMENTS: dict = _cfg["anatomy"]["segments"]


def muscle_moment_arm(muscle_name: str, joint_angle_rad: float) -> float:
    """
    Effective moment arm (m) at a given joint angle.
    Varies sinusoidally, peaking near 90° flexion/abduction.
    """
    p = MUSCLE_PARAMS[muscle_name]
    return p["ma_base"] * (1.0 + p["ma_var"] * np.sin(joint_angle_rad))


def muscle_max_force(muscle_name: str) -> float:
    """Maximum isometric force (N) for a muscle."""
    return MUSCLE_PARAMS[muscle_name]["fmax"]
