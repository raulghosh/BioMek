"""
Muscle parameters (arm26.osim / Holzbaur 2005), Thelen2003 force-length,
and Holzbaur 2005 moment-arm data fitted with natural cubic splines.
"""

import numpy as np
import yaml
from pathlib import Path
from scipy.interpolate import CubicSpline

_CONFIG_PATH = Path(__file__).parents[2] / "config" / "simulation.yaml"


def load_config(path: Path = _CONFIG_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


_cfg = load_config()
ELBOW_MUSCLES: dict    = _cfg["elbow_muscles"]
SHOULDER_MUSCLES: dict = _cfg["shoulder_muscles"]
WRIST_MUSCLES: dict    = _cfg["wrist_muscles"]
SEGMENTS: dict         = _cfg["segments"]
JOINT_REF_AREA: dict   = _cfg["joint_ref_areas"]
GRIP_FMAX: float       = _cfg["grip_fmax"]

MEDIAL_EPICONDYLE_CSA:  float = _cfg["epicondyles"]["medial"]["tendon_csa_m2"]
LATERAL_EPICONDYLE_CSA: float = _cfg["epicondyles"]["lateral"]["tendon_csa_m2"]

GRIP_PATTERN_EXTENSOR: dict = {
    p: v["extensor_cocontraction"]
    for p, v in _cfg["grip_patterns"].items()
}

FLEXORS   = ["BIClong", "BICshort", "BRA"]
EXTENSORS = ["TRIlong", "TRIlat",   "TRImed"]
ABDUCTORS = ["DELT_lat", "DELT_ant", "SUPSP"]


# ── arm26.osim moment-arm control points (virtual-work, Holzbaur 2005 Fig 4) ──
# Elbow angle (deg) → moment arm (m); positive = flexion, negative = extension
_E_DEG = np.array([0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150], dtype=float)
_E_RAD = np.radians(_E_DEG)

_BIClong_MA  = np.array([0.0102, 0.0188, 0.0270, 0.0343, 0.0406,
                          0.0455, 0.0481, 0.0480, 0.0438, 0.0341, 0.0179])
# BICshort path slightly shorter; scales at ~87 % of BIClong (Holzbaur 2005)
_BICshort_MA = _BIClong_MA * 0.875
_BRA_MA      = np.array([0.0154, 0.0160, 0.0166, 0.0170, 0.0174,
                          0.0177, 0.0178, 0.0176, 0.0172, 0.0165, 0.0155])
_TRIlong_MA  = np.array([-0.0211, -0.0220, -0.0230, -0.0238, -0.0243,
                          -0.0248, -0.0251, -0.0250, -0.0246, -0.0239, -0.0228])
_TRIlat_MA   = np.array([-0.0177, -0.0185, -0.0193, -0.0200, -0.0206,
                          -0.0210, -0.0213, -0.0213, -0.0210, -0.0204, -0.0194])

# Natural cubic splines (bc_type='not-a-knot' is scipy default)
_cs_BIClong  = CubicSpline(_E_RAD, _BIClong_MA)
_cs_BICshort = CubicSpline(_E_RAD, _BICshort_MA)
_cs_BRA      = CubicSpline(_E_RAD, _BRA_MA)
_cs_TRIlong  = CubicSpline(_E_RAD, _TRIlong_MA)
_cs_TRIlat   = CubicSpline(_E_RAD, _TRIlat_MA)


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


# ── Moment-arm functions ──────────────────────────────────────

def elbow_moment_arms(angles_rad) -> dict:
    """
    Moment arms (m) for elbow muscles vs elbow flexion angle.
    Natural cubic splines fitted to Holzbaur et al. 2005 / arm26.osim data.
    Positive = flexion; negative = extension.
    """
    a = np.asarray(angles_rad, dtype=float)
    return {
        "BIClong":  _cs_BIClong(a),
        "BICshort": _cs_BICshort(a),
        "BRA":      _cs_BRA(a),
        "TRIlong":  _cs_TRIlong(a),
        "TRIlat":   _cs_TRIlat(a),
        "TRImed":   _cs_TRIlat(a),   # TRImed ≈ TRIlat per Holzbaur 2005
    }


def shoulder_moment_arms(angles_rad) -> dict:
    """
    Moment arms (m) for shoulder abduction muscles vs abduction angle.
    Holzbaur 2005 approximations.
    """
    a = np.asarray(angles_rad, dtype=float)
    return {
        "DELT_lat": 0.025 * (1.0 + 1.8 * np.sin(a)),
        "DELT_ant": 0.020 * (1.0 + 1.2 * np.sin(a)),
        "SUPSP":    0.012 * (1.0 + 0.6 * np.sin(a)),
    }


def wrist_moment_arms(grip_pattern: str = "neutral") -> dict:
    """
    Wrist muscle moment arms (m) at the wrist joint.
    Constant approximations from Holzbaur 2005 Table 2.
    Positive = flexion, negative = extension.
    elbow_ma is the coupling contribution to elbow flexion torque.
    """
    return {
        "FCR":  {"wrist_ma": 0.020, "elbow_ma":  0.008},
        "FCU":  {"wrist_ma": 0.020, "elbow_ma":  0.000},
        "PL":   {"wrist_ma": 0.015, "elbow_ma":  0.000},
        "PT":   {"wrist_ma": 0.000, "elbow_ma":  0.014},
        "ECRB": {"wrist_ma":-0.015, "elbow_ma":  0.000},
        "ECRL": {"wrist_ma":-0.018, "elbow_ma":  0.009},
        "ECU":  {"wrist_ma":-0.012, "elbow_ma":  0.000},
    }


# ── Fiber length integration (Thelen 2003 via virtual work) ──

def normalized_fiber_lengths(angles_rad, moment_arm_fn, muscle_db, muscles) -> dict:
    """
    Normalized fiber lengths l / l_opt at each angle.
    Uses: dl_MT = -r dθ  (virtual work), with reference state at θ = π/2.
    """
    from scipy.integrate import cumulative_trapezoid
    theta_ref = np.pi / 2
    all_ma = moment_arm_fn(angles_rad)
    result = {}
    for m in muscles:
        p = muscle_db[m]
        l_ts    = p["tendon_slack_length"]
        l_opt   = p["optimal_fiber_length"]
        cos_pen = np.cos(p["pennation_angle"])
        l_mt_ref = l_ts + l_opt * cos_pen
        r = np.asarray(all_ma[m], dtype=float)
        integral_full     = cumulative_trapezoid(r, angles_rad, initial=0.0)
        idx_ref           = int(np.argmin(np.abs(angles_rad - theta_ref)))
        integral_from_ref = integral_full - integral_full[idx_ref]
        l_mt    = l_mt_ref - integral_from_ref
        l_fiber = np.clip((l_mt - l_ts) / cos_pen, 1e-4, None)
        result[m] = l_fiber / l_opt
    return result
