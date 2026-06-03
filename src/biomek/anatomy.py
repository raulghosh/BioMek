"""
Muscle parameters (arm26.osim / Holzbaur 2005), Thelen2003 force-length,
and Holzbaur 2005 moment-arm polynomial fits.
"""

import numpy as np
import yaml
from pathlib import Path

_CONFIG_PATH = Path(__file__).parents[2] / "config" / "simulation.yaml"


def load_config(path: Path = _CONFIG_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


_cfg = load_config()
ELBOW_MUSCLES: dict   = _cfg["elbow_muscles"]
SHOULDER_MUSCLES: dict = _cfg["shoulder_muscles"]
SEGMENTS: dict         = _cfg["segments"]
JOINT_REF_AREA: dict   = _cfg["joint_ref_areas"]
GRIP_FMAX: float       = _cfg["grip_fmax"]

# Epicondyle tendon cross-sectional areas (m²) — from anatomical cadaveric studies
MEDIAL_EPICONDYLE_CSA:  float = _cfg["epicondyles"]["medial"]["tendon_csa_m2"]
LATERAL_EPICONDYLE_CSA: float = _cfg["epicondyles"]["lateral"]["tendon_csa_m2"]

# ECRB extensor co-contraction fraction relative to grip force, per grip orientation
GRIP_PATTERN_EXTENSOR: dict = {
    p: v["extensor_cocontraction"]
    for p, v in _cfg["grip_patterns"].items()
}

FLEXORS   = ["BIClong", "BICshort", "BRA"]
EXTENSORS = ["TRIlong", "TRIlat",   "TRImed"]
ABDUCTORS = ["DELT_lat", "DELT_ant", "SUPSP"]


# ── Thelen2003 force-length ───────────────────────────────────

def thelen_active_force_length(norm_fiber_length: float, gamma: float = 0.5) -> float:
    """Active force-length (Thelen 2003). Returns scalar in [0,1]."""
    return np.exp(-((norm_fiber_length - 1.0) ** 2) / gamma)


def thelen_passive_force_length(norm_fiber_length, kPE: float = 4.0, e0: float = 0.6):
    """Passive force-length (Thelen 2003). Zero for compressed fibers."""
    strain = norm_fiber_length - 1.0
    if np.isscalar(strain):
        if strain <= 0:
            return 0.0
        return (np.exp(kPE * strain / e0) - 1.0) / (np.exp(kPE) - 1.0)
    result = np.zeros_like(np.asarray(strain, dtype=float))
    mask = strain > 0
    result[mask] = (np.exp(kPE * strain[mask] / e0) - 1.0) / (np.exp(kPE) - 1.0)
    return result


# ── Holzbaur 2005 moment-arm fits ────────────────────────────

def elbow_moment_arms(angles_rad) -> dict:
    """
    Moment arms (m) for elbow muscles vs elbow flexion angle.
    Polynomial fits to Holzbaur et al. 2005, Fig. 4.
    Positive = flexion; negative = extension.
    """
    a = np.asarray(angles_rad)
    return {
        # Biceps long head: peaks ~4.8 cm near 80° (1.4 rad)
        "BIClong":  0.048 * np.sin(0.88*a + 0.25) * np.clip(1.0 - 0.12*(a-1.4)**2, 0.55, 1.0),
        # Biceps short head: slightly smaller
        "BICshort": 0.042 * np.sin(0.88*a + 0.25) * np.clip(1.0 - 0.12*(a-1.4)**2, 0.55, 1.0),
        # Brachialis: broad peak ~1.8 cm
        "BRA":      0.018 * (1.0 + 0.35 * np.sin(a * 0.9 + 0.1)),
        # Triceps (extensors — negative)
        "TRIlong":  -0.024 * (1.0 + 0.18 * np.sin(a * 0.8)),
        "TRIlat":   -0.021 * (1.0 + 0.15 * np.sin(a * 0.8)),
        "TRImed":   -0.021 * (1.0 + 0.15 * np.sin(a * 0.8)),
    }


def shoulder_moment_arms(angles_rad) -> dict:
    """
    Moment arms (m) for shoulder abduction muscles vs abduction angle.
    Holzbaur 2005 approximations.
    """
    a = np.asarray(angles_rad)
    return {
        "DELT_lat": 0.025 * (1.0 + 1.8 * np.sin(a)),
        "DELT_ant": 0.020 * (1.0 + 1.2 * np.sin(a)),
        "SUPSP":    0.012 * (1.0 + 0.6 * np.sin(a)),
    }
