"""
BioMek Forearm Device — Standalone Biomechanical Simulation
=============================================================
Uses validated muscle parameters from the OpenSim arm26 model (Holzbaur et al.
2005) and Thelen2003 muscle dynamics. Does NOT require OpenSim installed —
all parameters are embedded directly from the peer-reviewed model.

For the full OpenSim version, see biomek_opensim.py.

Exercises simulated:
  1. Standard Cable Curl (supinated grip)
  2. Reverse Cable Curl (pronated grip)
  3. Lateral Raise (requires shoulder model approximation)

Usage:
    python biomek_sim.py [--force 50]

References:
    Holzbaur KRS, Murray WM, Delp SL (2005). Annals of Biomed Eng, 33: 829-840.
    Thelen DG (2003). J Biomech Eng, 125: 70-77.
    arm26.osim: https://github.com/opensim-org/opensim-models/tree/master/Models/Arm26
"""

import os
import sys
import argparse
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# SECTION 1: Muscle Parameters (from arm26.osim, Thelen2003)
# ============================================================

# Exact values extracted from:
# https://github.com/opensim-org/opensim-models/blob/master/Models/Arm26/arm26.osim

ELBOW_MUSCLES = {
    "BIClong": {
        "full_name": "Biceps Long Head",
        "max_isometric_force": 624.3,    # N
        "optimal_fiber_length": 0.1157,  # m
        "tendon_slack_length": 0.2723,   # m
        "pennation_angle": 0.0,          # rad
        "KshapeActive": 0.5,
        "FmaxMuscleStrain": 0.6,
        "role": "flexor",
    },
    "BICshort": {
        "full_name": "Biceps Short Head",
        "max_isometric_force": 435.56,
        "optimal_fiber_length": 0.1321,
        "tendon_slack_length": 0.1923,
        "pennation_angle": 0.0,
        "KshapeActive": 0.5,
        "FmaxMuscleStrain": 0.6,
        "role": "flexor",
    },
    "BRA": {
        "full_name": "Brachialis",
        "max_isometric_force": 987.26,
        "optimal_fiber_length": 0.0858,
        "tendon_slack_length": 0.0535,
        "pennation_angle": 0.0,
        "KshapeActive": 0.5,
        "FmaxMuscleStrain": 0.6,
        "role": "flexor",
    },
    "TRIlong": {
        "full_name": "Triceps Long Head",
        "max_isometric_force": 798.52,
        "optimal_fiber_length": 0.134,
        "tendon_slack_length": 0.143,
        "pennation_angle": 0.2094,
        "KshapeActive": 0.5,
        "FmaxMuscleStrain": 0.6,
        "role": "extensor",
    },
    "TRIlat": {
        "full_name": "Triceps Lateral Head",
        "max_isometric_force": 624.3,
        "optimal_fiber_length": 0.1138,
        "tendon_slack_length": 0.098,
        "pennation_angle": 0.1571,
        "KshapeActive": 0.5,
        "FmaxMuscleStrain": 0.6,
        "role": "extensor",
    },
    "TRImed": {
        "full_name": "Triceps Medial Head",
        "max_isometric_force": 624.3,
        "optimal_fiber_length": 0.1138,
        "tendon_slack_length": 0.0908,
        "pennation_angle": 0.1571,
        "KshapeActive": 0.5,
        "FmaxMuscleStrain": 0.6,
        "role": "extensor",
    },
}

# Shoulder muscles — approximate values from Holzbaur 2005 full upper extremity model
SHOULDER_MUSCLES = {
    "DELT_lat": {
        "full_name": "Deltoid Lateral",
        "max_isometric_force": 1142.6,
        "optimal_fiber_length": 0.0838,
        "tendon_slack_length": 0.038,
        "pennation_angle": 0.2618,  # 15°
        "KshapeActive": 0.5,
        "FmaxMuscleStrain": 0.6,
        "role": "abductor",
    },
    "DELT_ant": {
        "full_name": "Deltoid Anterior",
        "max_isometric_force": 1218.9,
        "optimal_fiber_length": 0.0976,
        "tendon_slack_length": 0.093,
        "pennation_angle": 0.3840,  # 22°
        "KshapeActive": 0.5,
        "FmaxMuscleStrain": 0.6,
        "role": "abductor",
    },
    "SUPSP": {
        "full_name": "Supraspinatus",
        "max_isometric_force": 487.8,
        "optimal_fiber_length": 0.0682,
        "tendon_slack_length": 0.040,
        "pennation_angle": 0.1222,  # 7°
        "KshapeActive": 0.5,
        "FmaxMuscleStrain": 0.6,
        "role": "abductor",
    },
}

# Segment geometry (meters)
UPPER_ARM_LENGTH = 0.2817
FOREARM_LENGTH = 0.2534
HAND_GRIP_CENTER = 0.05
DEVICE_PAD_FROM_WRIST = 0.02

# Joint stress normalization areas (m²)
JOINT_REF_AREA = {"wrist": 0.0006, "elbow": 0.0012, "shoulder": 0.0020}

FLEXORS = ["BIClong", "BICshort", "BRA"]
EXTENSORS = ["TRIlong", "TRIlat", "TRImed"]
ABDUCTORS = ["DELT_lat", "DELT_ant", "SUPSP"]


# ============================================================
# SECTION 2: Thelen2003 Force-Length Model
# ============================================================

def thelen_active_force_length(norm_fiber_length, gamma=0.5):
    """
    Thelen2003 active force-length relationship.
    Returns normalized force [0, 1] as a function of normalized fiber length.

    Parameters
    ----------
    norm_fiber_length : float or array — l_fiber / l_optimal
    gamma : float — shape factor (KshapeActive, default 0.5)
    """
    return np.exp(-((norm_fiber_length - 1.0) ** 2) / gamma)


def thelen_passive_force_length(norm_fiber_length, kPE=4.0, e0=0.6):
    """
    Thelen2003 passive force-length relationship.

    Parameters
    ----------
    norm_fiber_length : float or array
    kPE : float — KshapePassive (default 4.0)
    e0 : float — FmaxMuscleStrain (default 0.6)
    """
    strain = norm_fiber_length - 1.0
    if np.isscalar(strain):
        if strain <= 0:
            return 0.0
        return (np.exp(kPE * strain / e0) - 1.0) / (np.exp(kPE) - 1.0)
    result = np.zeros_like(strain)
    mask = strain > 0
    result[mask] = (np.exp(kPE * strain[mask] / e0) - 1.0) / (np.exp(kPE) - 1.0)
    return result


def max_muscle_force_at_length(muscle_params, norm_fiber_length, activation=1.0):
    """
    Maximum force a muscle can produce at a given fiber length and activation.
    Uses Thelen2003 model: F = Fmax * [a * f_AL(l̃) + f_PL(l̃)] * cos(pennation)

    Parameters
    ----------
    muscle_params : dict — from ELBOW_MUSCLES or SHOULDER_MUSCLES
    norm_fiber_length : float
    activation : float — [0, 1]

    Returns
    -------
    float — force in Newtons
    """
    f_al = thelen_active_force_length(norm_fiber_length, muscle_params["KshapeActive"])
    f_pl = thelen_passive_force_length(norm_fiber_length, 4.0, muscle_params["FmaxMuscleStrain"])
    cos_penn = np.cos(muscle_params["pennation_angle"])
    return muscle_params["max_isometric_force"] * (activation * f_al + f_pl) * cos_penn


# ============================================================
# SECTION 3: Moment Arm Models (from Holzbaur 2005 data)
# ============================================================

def elbow_moment_arms(angles_rad):
    """
    Moment arms (m) for elbow muscles as a function of elbow flexion angle.
    Fit to published data from Holzbaur et al. 2005, Fig. 4.
    Positive = flexion moment arm.

    Parameters
    ----------
    angles_rad : array — elbow flexion angles (0 = full extension)

    Returns
    -------
    dict : {muscle_name: array of moment arms in meters}
    """
    a = angles_rad
    ma = {}

    # Biceps long head: peaks ~4.8 cm at ~80° (1.4 rad)
    ma["BIClong"] = 0.048 * np.sin(0.88 * a + 0.25) * np.clip(
        1.0 - 0.12 * (a - 1.4)**2, 0.55, 1.0)

    # Biceps short head: peaks ~4.2 cm at ~80°
    ma["BICshort"] = 0.042 * np.sin(0.88 * a + 0.25) * np.clip(
        1.0 - 0.12 * (a - 1.4)**2, 0.55, 1.0)

    # Brachialis: peaks ~1.8 cm, broad peak
    ma["BRA"] = 0.018 * (1.0 + 0.35 * np.sin(a * 0.9 + 0.1))

    # Triceps — negative (extensors)
    ma["TRIlong"] = -0.024 * (1.0 + 0.18 * np.sin(a * 0.8))
    ma["TRIlat"]  = -0.021 * (1.0 + 0.15 * np.sin(a * 0.8))
    ma["TRImed"]  = -0.021 * (1.0 + 0.15 * np.sin(a * 0.8))

    return ma


def shoulder_moment_arms(angles_rad):
    """
    Moment arms for shoulder abduction muscles (Holzbaur 2005 approximations).
    Positive = abduction moment arm.

    Parameters
    ----------
    angles_rad : array — shoulder abduction angles (0 = arm at side)
    """
    a = angles_rad
    ma = {}
    # Lateral deltoid: peaks ~2.5 cm at ~60-90° abduction
    ma["DELT_lat"] = 0.025 * (1.0 + 1.8 * np.sin(a))
    # Anterior deltoid: peaks ~2 cm
    ma["DELT_ant"] = 0.020 * (1.0 + 1.2 * np.sin(a))
    # Supraspinatus: peaks ~1.2 cm, broad
    ma["SUPSP"] = 0.012 * (1.0 + 0.6 * np.sin(a))
    return ma


# ============================================================
# SECTION 4: Equipment Model
# ============================================================

class Equipment:
    def __init__(self, mode):
        assert mode in ("traditional", "biomek")
        self.mode = mode

    @property
    def label(self):
        return "Traditional" if self.mode == "traditional" else "BioMek"

    def elbow_force_distance(self):
        if self.mode == "traditional":
            return FOREARM_LENGTH + HAND_GRIP_CENTER
        return FOREARM_LENGTH - DEVICE_PAD_FROM_WRIST

    def shoulder_force_distance(self):
        if self.mode == "traditional":
            return UPPER_ARM_LENGTH + FOREARM_LENGTH + HAND_GRIP_CENTER
        return UPPER_ARM_LENGTH + FOREARM_LENGTH - DEVICE_PAD_FROM_WRIST

    def grip_fraction(self):
        return 1.0 if self.mode == "traditional" else 0.05

    def wrist_torque(self, F):
        return F * HAND_GRIP_CENTER if self.mode == "traditional" else 0.0


# ============================================================
# SECTION 5: Exercise Definitions
# ============================================================

class Exercise:
    def __init__(self, name, joint, angle_range_deg, muscles, moment_arm_fn,
                 muscle_db, grip_Fmax=600.0):
        self.name = name
        self.joint = joint  # "elbow" or "shoulder"
        self.angle_range_deg = angle_range_deg
        self.muscles = muscles  # list of muscle names
        self.moment_arm_fn = moment_arm_fn
        self.muscle_db = muscle_db
        self.grip_Fmax = grip_Fmax


EXERCISES = [
    Exercise("Standard Curl", "elbow", (10, 140),
             FLEXORS + EXTENSORS, elbow_moment_arms, ELBOW_MUSCLES),
    Exercise("Reverse Curl", "elbow", (10, 140),
             FLEXORS + EXTENSORS, elbow_moment_arms, ELBOW_MUSCLES),
    Exercise("Lateral Raise", "shoulder", (5, 90),
             ABDUCTORS, shoulder_moment_arms, SHOULDER_MUSCLES),
]


# ============================================================
# SECTION 6: Static Optimization
# ============================================================

def solve_static_optimization(tau_required, moment_arms_at_angle, muscle_db,
                              muscle_list):
    """
    Minimize sum(a_i^2) subject to torque balance: sum(a_i * c_i) = tau.
    Solved analytically using Lagrange multipliers (no scipy needed).

    For the equality-constrained QP with box constraints [0, 1]:
        c_i = Fmax_i × cos(penn_i) × ma_i
        Unconstrained: a_i = lambda × c_i / 2
        lambda = 2 × tau / sum(c_i^2)

    Then iteratively handle box constraints by clamping and redistributing.
    """
    n = len(muscle_list)
    if n == 0:
        return {}, {}

    Fmax = np.array([muscle_db[m]["max_isometric_force"] for m in muscle_list])
    ma = np.array([moment_arms_at_angle.get(m, 0.0) for m in muscle_list])
    penn = np.array([muscle_db[m]["pennation_angle"] for m in muscle_list])
    cos_penn = np.cos(penn)

    # c_i = torque capacity coefficient for muscle i
    c = Fmax * cos_penn * ma  # torque per unit activation

    # Only use muscles that contribute in the right direction
    # For positive tau, use muscles with positive c (flexors for flexion torque)
    if tau_required >= 0:
        active_mask = c > 1e-6
    else:
        active_mask = c < -1e-6

    if not np.any(active_mask):
        # No muscles can produce required torque direction — return zeros
        return {m: 0.0 for m in muscle_list}, {m: 0.0 for m in muscle_list}

    c_active = c[active_mask]
    sum_c2 = np.sum(c_active**2)

    if sum_c2 < 1e-12:
        return {m: 0.0 for m in muscle_list}, {m: 0.0 for m in muscle_list}

    # Analytical solution
    lam = 2.0 * tau_required / sum_c2
    a_all = np.zeros(n)
    a_all[active_mask] = lam * c_active / 2.0

    # Clamp to [0, 1] and redistribute if needed (iterative)
    for _ in range(5):
        clamped_low = a_all < 0
        clamped_high = a_all > 1
        a_all[clamped_low] = 0.0
        a_all[clamped_high] = 1.0

        # Check residual torque
        tau_achieved = np.sum(a_all * c)
        tau_deficit = tau_required - tau_achieved

        if abs(tau_deficit) < 1e-6:
            break

        # Redistribute deficit among unclamped muscles
        free = ~clamped_low & ~clamped_high & active_mask
        c_free = c[free]
        sum_c2_free = np.sum(c_free**2)
        if sum_c2_free < 1e-12:
            break
        delta_lam = 2.0 * tau_deficit / sum_c2_free
        a_all[free] += delta_lam * c_free / 2.0

    # Final clamp
    a_all = np.clip(a_all, 0.0, 1.0)

    acts = {}
    forces = {}
    for i, m in enumerate(muscle_list):
        acts[m] = float(a_all[i])
        forces[m] = float(a_all[i] * Fmax[i] * cos_penn[i])
    return acts, forces


# ============================================================
# SECTION 7: Simulation Engine
# ============================================================

def run_simulation(exercise, equipment, F_cable, n_points=60):
    """Run simulation across full ROM for one exercise + equipment combo."""
    a_min, a_max = exercise.angle_range_deg
    angles_deg = np.linspace(a_min, a_max, n_points)
    angles_rad = np.radians(angles_deg)

    # Compute moment arms across ROM
    all_ma = exercise.moment_arm_fn(angles_rad)

    # Get force application distance
    if exercise.joint == "elbow":
        L = equipment.elbow_force_distance()
    else:
        L = equipment.shoulder_force_distance()

    # Storage
    activations = {m: np.zeros(n_points) for m in exercise.muscles}
    forces = {m: np.zeros(n_points) for m in exercise.muscles}
    grip_act = np.zeros(n_points)
    wrist_stress = np.zeros(n_points)
    elbow_stress = np.zeros(n_points)
    shoulder_stress = np.zeros(n_points)

    for i, (a_deg, a_rad) in enumerate(zip(angles_deg, angles_rad)):
        # External torque about joint
        tau_ext = F_cable * L * np.sin(a_rad)

        # Moment arms at this angle
        ma_i = {m: all_ma[m][i] for m in exercise.muscles}

        # Static optimization
        acts, frc = solve_static_optimization(
            tau_ext, ma_i, exercise.muscle_db, exercise.muscles)

        for m in exercise.muscles:
            activations[m][i] = acts.get(m, 0.0) * 100  # to %MVC
            forces[m][i] = frc.get(m, 0.0)

        # Grip
        grip_force = equipment.grip_fraction() * F_cable
        grip_act[i] = (grip_force / exercise.grip_Fmax) * 100

        # Wrist stress
        tau_w = equipment.wrist_torque(F_cable)
        wf = np.sqrt(grip_force**2 + (tau_w / 0.02)**2)
        wrist_stress[i] = wf / JOINT_REF_AREA["wrist"]

        # Elbow stress
        if exercise.joint == "elbow":
            total_mf = sum(frc.values())
            ef = np.sqrt(total_mf**2 + (F_cable * np.cos(a_rad))**2)
            elbow_stress[i] = ef / JOINT_REF_AREA["elbow"]
        else:
            elbow_stress[i] = (F_cable * 0.1) / JOINT_REF_AREA["elbow"]

        # Shoulder stress (for lateral raise)
        if exercise.joint == "shoulder":
            total_mf = sum(frc.values())
            shoulder_stress[i] = total_mf / JOINT_REF_AREA["shoulder"]

    # Peaks
    peak_act = {m: float(np.max(activations[m])) for m in exercise.muscles}
    peak_act["grip"] = float(np.max(grip_act))

    return {
        "exercise": exercise.name,
        "equipment": equipment.label,
        "angles_deg": angles_deg,
        "activations": activations,
        "grip_activation": grip_act,
        "forces": forces,
        "wrist_stress": wrist_stress,
        "elbow_stress": elbow_stress,
        "shoulder_stress": shoulder_stress,
        "peak_activations": peak_act,
        "peak_wrist_stress": float(np.max(wrist_stress)),
        "peak_elbow_stress": float(np.max(elbow_stress)),
        "peak_shoulder_stress": float(np.max(shoulder_stress)),
    }


# ============================================================
# SECTION 8: Visualization
# ============================================================

# Colors
MC = {
    "BIClong": "#e74c3c", "BICshort": "#c0392b", "BRA": "#e67e22",
    "TRIlong": "#3498db", "TRIlat": "#2980b9", "TRImed": "#1abc9c",
    "DELT_lat": "#3498db", "DELT_ant": "#2980b9", "SUPSP": "#8e44ad",
    "grip": "#95a5a6",
}


def plot_equipment_schematic(fig):
    """Draw top-down schematic of the BioMek device."""
    ax = fig.add_subplot(111)
    ax.set_xlim(-2, 12)
    ax.set_ylim(-2, 8)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("BioMek Forearm Device — Top View", fontsize=16, fontweight="bold", pad=20)

    rect = mpatches.FancyBboxPatch(
        (1, 1), 8, 5, boxstyle="round,pad=0.2",
        facecolor="none", edgecolor="#2c3e50", linewidth=3)
    ax.add_patch(rect)

    pad = mpatches.FancyBboxPatch(
        (1, 0.3), 8, 1.4, boxstyle="round,pad=0.3",
        facecolor="#a8d8ea", edgecolor="#3498db", linewidth=2, alpha=0.7)
    ax.add_patch(pad)
    ax.text(5, 1.0, 'PADDED ARM (on forearm bone)', ha='center', va='center',
            fontsize=9, fontweight='bold', color='#2c3e50')

    palm = mpatches.FancyBboxPatch(
        (1, 5.3), 8, 0.7, boxstyle="round,pad=0.1",
        facecolor="#fadbd8", edgecolor="#e74c3c", linewidth=2, alpha=0.7)
    ax.add_patch(palm)
    ax.text(5, 5.65, 'PALM REST ARM (stabilizer)', ha='center', va='center',
            fontsize=9, fontweight='bold', color='#922b21')

    for x in [1.2, 8.8]:
        ax.plot([x, x], [1.7, 5.3], color='#7f8c8d', linewidth=6, solid_capstyle='round')

    ax.annotate('', xy=(9.5, 1), xytext=(9.5, 6),
                arrowprops=dict(arrowstyle='<->', color='#2c3e50', lw=1.5))
    ax.text(10.2, 3.5, '6"', fontsize=12, ha='center', va='center')
    ax.annotate('', xy=(1, 7), xytext=(9, 7),
                arrowprops=dict(arrowstyle='<->', color='#2c3e50', lw=1.5))
    ax.text(5, 7.4, '6" (long arms)', fontsize=10, ha='center')
    ax.annotate('', xy=(0.3, 1.7), xytext=(0.3, 5.3),
                arrowprops=dict(arrowstyle='<->', color='#7f8c8d', lw=1.2))
    ax.text(-0.5, 3.5, '3"', fontsize=10, ha='center', va='center', color='#7f8c8d')

    ax.plot([0.2, -0.5, -0.5, 0.2], [1.0, 0.5, -0.5, -1.0],
            color='#27ae60', linewidth=3, linestyle='--')
    ax.plot([9.8, 10.5, 10.5, 9.8], [1.0, 0.5, -0.5, -1.0],
            color='#27ae60', linewidth=3, linestyle='--')
    ax.text(5, -1.2, 'HARNESS LOOP (clips to cable carabiner)',
            ha='center', fontsize=10, color='#27ae60', fontweight='bold')


def plot_muscle_comparison(fig, all_results):
    """Bar charts: peak muscle activation per exercise."""
    n_ex = len(all_results)
    gs = GridSpec(1, n_ex, figure=fig, wspace=0.35)

    for idx, (exercise, res_dev, res_trad) in enumerate(all_results):
        ax = fig.add_subplot(gs[0, idx])
        muscles = exercise.muscles + ["grip"]

        dev_vals = [res_dev["peak_activations"].get(m, 0) for m in muscles]
        trad_vals = [res_trad["peak_activations"].get(m, 0) for m in muscles]
        colors = [MC.get(m, "#bdc3c7") for m in muscles]

        x = np.arange(len(muscles))
        w = 0.35

        ax.bar(x - w/2, trad_vals, w, color=colors, alpha=0.4,
               edgecolor="black", linewidth=0.5)
        ax.bar(x + w/2, dev_vals, w, color=colors, alpha=1.0,
               edgecolor="black", linewidth=1.2)

        for j, (tv, dv) in enumerate(zip(trad_vals, dev_vals)):
            if tv > 0.5:
                ax.text(x[j] - w/2, tv + 0.3, f'{tv:.0f}%', ha='center',
                        fontsize=6, color='#888')
            if dv > 0.5:
                ax.text(x[j] + w/2, dv + 0.3, f'{dv:.0f}%', ha='center',
                        fontsize=6, fontweight='bold')

        labels = [m.replace("_", "\n") for m in muscles]
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=7)
        ax.set_ylabel("Peak Activation (%MVC)" if idx == 0 else "")
        ax.set_title(exercise.name, fontsize=12, fontweight="bold")
        ax.set_ylim(0, max(max(dev_vals + [1]), max(trad_vals + [1])) * 1.3 + 2)

        if idx == 0:
            handles = [
                mpatches.Patch(facecolor='gray', alpha=0.4, label='Traditional'),
                mpatches.Patch(facecolor='gray', alpha=1.0, label='BioMek'),
            ]
            ax.legend(handles=handles, fontsize=7, loc='upper left')


def plot_joint_stress(fig, all_results):
    """Grouped bar chart: joint stress for all exercises."""
    ax = fig.add_subplot(111)
    names = [ex.name for ex, _, _ in all_results]
    joints = ["wrist", "elbow", "shoulder"]
    jcolors = {"wrist": "#e74c3c", "elbow": "#f39c12", "shoulder": "#3498db"}

    x = np.arange(len(names))
    n_j = len(joints)
    total_w = 0.7
    bw = total_w / (n_j * 2)

    for ji, j in enumerate(joints):
        off_t = -total_w/2 + ji * 2 * bw + bw * 0.5
        off_d = off_t + bw

        key = f"peak_{j}_stress"
        vt = [res_trad.get(key, 0) / 1000 for _, _, res_trad in all_results]
        vd = [res_dev.get(key, 0) / 1000 for _, res_dev, _ in all_results]

        ax.bar(x + off_t, vt, bw, color=jcolors[j], alpha=0.4,
               edgecolor='black', linewidth=0.5, label=f'{j.title()} (Trad)')
        ax.bar(x + off_d, vd, bw, color=jcolors[j], alpha=1.0,
               edgecolor='black', linewidth=1.0, label=f'{j.title()} (BioMek)')

        for i in range(len(names)):
            if vt[i] > 0.5:
                red = (1 - vd[i] / vt[i]) * 100
                if red > 3:
                    ax.text(x[i] + off_d, max(vt[i], vd[i]) + 3,
                            f'-{red:.0f}%', ha='center', fontsize=7,
                            color=jcolors[j], fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=11)
    ax.set_ylabel("Peak Joint Stress (kPa)")
    ax.set_title("Joint Stress: BioMek vs Traditional (arm26 parameters)",
                 fontsize=13, fontweight="bold")
    ax.legend(fontsize=7, ncol=3, loc='upper right')
    ax.grid(axis='y', alpha=0.3)


def plot_rom_sweep(fig, all_results):
    """ROM sweep: activation and stress line plots."""
    n_ex = len(all_results)
    gs = GridSpec(n_ex, 2, figure=fig, hspace=0.55, wspace=0.3)

    for idx, (exercise, res_dev, res_trad) in enumerate(all_results):
        angles = res_dev["angles_deg"]

        ax1 = fig.add_subplot(gs[idx, 0])
        for m in exercise.muscles:
            c = MC.get(m, "#bdc3c7")
            ax1.plot(angles, res_trad["activations"][m], '--', color=c,
                     alpha=0.5, linewidth=1.5)
            ax1.plot(angles, res_dev["activations"][m], '-', color=c,
                     linewidth=2, label=m)
        ax1.plot(angles, res_trad["grip_activation"], '--', color='gray', alpha=0.5)
        ax1.plot(angles, res_dev["grip_activation"], '-', color='gray', linewidth=2, label="Grip")
        ax1.set_xlabel(f'{exercise.joint.title()} Angle (deg)', fontsize=9)
        ax1.set_ylabel('Activation (%MVC)', fontsize=9)
        ax1.set_title(f'{exercise.name} — Muscle Activation', fontsize=10, fontweight='bold')
        ax1.legend(fontsize=6, loc='upper left')
        ax1.grid(alpha=0.3)
        if idx == 0:
            ax1.text(0.98, 0.02, 'Solid=BioMek, Dashed=Traditional',
                     transform=ax1.transAxes, fontsize=6, ha='right', va='bottom',
                     style='italic', color='#999')

        ax2 = fig.add_subplot(gs[idx, 1])
        ax2.plot(angles, res_trad["wrist_stress"]/1000, '--', color='red', alpha=0.5)
        ax2.plot(angles, res_dev["wrist_stress"]/1000, '-', color='red', linewidth=2, label="Wrist")
        ax2.plot(angles, res_trad["elbow_stress"]/1000, '--', color='orange', alpha=0.5)
        ax2.plot(angles, res_dev["elbow_stress"]/1000, '-', color='orange', linewidth=2, label="Elbow")
        if exercise.joint == "shoulder":
            ax2.plot(angles, res_trad["shoulder_stress"]/1000, '--', color='blue', alpha=0.5)
            ax2.plot(angles, res_dev["shoulder_stress"]/1000, '-', color='blue', linewidth=2, label="Shoulder")
        ax2.set_xlabel(f'{exercise.joint.title()} Angle (deg)', fontsize=9)
        ax2.set_ylabel('Stress (kPa)', fontsize=9)
        ax2.set_title(f'{exercise.name} — Joint Stress', fontsize=10, fontweight='bold')
        ax2.legend(fontsize=6, loc='upper left')
        ax2.grid(alpha=0.3)


def plot_summary(fig, all_results, F_cable):
    """Summary dashboard."""
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)

    ax.text(5, 9.5, "BioMek Device — Impact Summary",
            fontsize=16, fontweight="bold", ha="center", color="#2c3e50")
    ax.text(5, 9.0, f"Cable: {F_cable:.0f}N ({F_cable*0.2248:.1f}lbs) | "
            "Muscle model: Thelen2003 | Source: arm26.osim (Holzbaur 2005)",
            fontsize=9, ha="center", color="#7f8c8d")

    y = 8.2
    for exercise, res_dev, res_trad in all_results:
        ax.text(0.5, y, exercise.name, fontsize=13, fontweight="bold", color="#2c3e50")
        y -= 0.45

        ws = res_trad["peak_wrist_stress"]
        ws_red = (1 - res_dev["peak_wrist_stress"] / ws) * 100 if ws > 0 else 0
        es = res_trad["peak_elbow_stress"]
        es_red = (1 - res_dev["peak_elbow_stress"] / es) * 100 if es > 0 else 0
        gr = res_trad["peak_activations"]["grip"]
        gr_red = (1 - res_dev["peak_activations"]["grip"] / gr) * 100 if gr > 0 else 0

        ax.text(1.0, y, f"Wrist: -{ws_red:.0f}%", fontsize=11, color="#e74c3c")
        ax.text(3.8, y, f"Elbow: -{es_red:.0f}%", fontsize=11, color="#f39c12")
        ax.text(6.5, y, f"Grip: -{gr_red:.0f}%", fontsize=11, color="#95a5a6")
        y -= 0.4

        active_muscles = [m for m in exercise.muscles
                          if exercise.muscle_db[m]["role"] != "extensor"]
        for m in active_muscles:
            pd = res_dev["peak_activations"].get(m, 0)
            pt = res_trad["peak_activations"].get(m, 0)
            ratio = pd / pt * 100 if pt > 0 else 0
            name = exercise.muscle_db[m]["full_name"]
            ax.text(1.0, y, f"  {name}: {pd:.1f}% MVC ({ratio:.0f}% of traditional)",
                    fontsize=8, color="#555")
            y -= 0.3
        y -= 0.3

    ax.text(0.5, y, "Key Takeaway:", fontsize=11, fontweight="bold", color="#27ae60")
    y -= 0.35
    ax.text(0.5, y, "Device virtually eliminates wrist stress and grip demand.",
            fontsize=10, color="#2c3e50")
    y -= 0.3
    ax.text(0.5, y, "Increase cable weight ~25-30% to match traditional muscle stimulus.",
            fontsize=10, color="#2c3e50")


# ============================================================
# SECTION 9: Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="BioMek Standalone Simulation")
    parser.add_argument("--force", type=float, default=50.0,
                        help="Cable force in Newtons (default: 50)")
    args = parser.parse_args()
    F_cable = args.force

    print("=" * 60)
    print("BioMek Device — Standalone Simulation (arm26 parameters)")
    print("=" * 60)
    print(f"Cable: {F_cable:.0f} N ({F_cable * 0.2248:.1f} lbs)")
    print(f"Muscle model: Thelen2003 | Source: arm26.osim (Holzbaur 2005)\n")

    eq_trad = Equipment("traditional")
    eq_dev = Equipment("biomek")

    all_results = []  # (exercise, res_dev, res_trad)

    for ex in EXERCISES:
        print(f"--- {ex.name} ---")
        res_trad = run_simulation(ex, eq_trad, F_cable)
        res_dev = run_simulation(ex, eq_dev, F_cable)
        all_results.append((ex, res_dev, res_trad))

        active = [m for m in ex.muscles if ex.muscle_db[m]["role"] != "extensor"]
        for m in active + ["grip"]:
            name = m if m == "grip" else ex.muscle_db[m]["full_name"]
            pt = res_trad["peak_activations"].get(m, 0)
            pd = res_dev["peak_activations"].get(m, 0)
            print(f"  {name:25s}  Trad: {pt:5.1f}%  Device: {pd:5.1f}%")

        for j in ["wrist", "elbow", "shoulder"]:
            key = f"peak_{j}_stress"
            st = res_trad.get(key, 0)
            sd = res_dev.get(key, 0)
            if st > 0.1:
                red = (1 - sd / st) * 100
                print(f"  {j.title():12s} stress   Trad: {st/1000:6.1f} kPa  "
                      f"Device: {sd/1000:6.1f} kPa  (down {red:.0f}%)")
        print()

    # --- Generate figures ---
    print("Generating visualizations...")

    fig0 = plt.figure(figsize=(12, 7))
    plot_equipment_schematic(fig0)
    fig0.savefig(os.path.join(OUTPUT_DIR, "equipment_schematic.png"),
                 dpi=150, bbox_inches="tight")
    print("  equipment_schematic.png")

    fig1 = plt.figure(figsize=(16, 5))
    fig1.suptitle("Peak Muscle Activation — BioMek vs Traditional (arm26 parameters)",
                  fontsize=13, fontweight="bold", y=1.02)
    plot_muscle_comparison(fig1, all_results)
    fig1.savefig(os.path.join(OUTPUT_DIR, "muscle_activation.png"),
                 dpi=150, bbox_inches="tight")
    print("  muscle_activation.png")

    fig2 = plt.figure(figsize=(12, 6))
    plot_joint_stress(fig2, all_results)
    fig2.savefig(os.path.join(OUTPUT_DIR, "joint_stress.png"),
                 dpi=150, bbox_inches="tight")
    print("  joint_stress.png")

    fig3 = plt.figure(figsize=(14, 12))
    fig3.suptitle("ROM Analysis — BioMek vs Traditional (arm26 parameters)",
                  fontsize=13, fontweight="bold")
    plot_rom_sweep(fig3, all_results)
    fig3.savefig(os.path.join(OUTPUT_DIR, "rom_sweep.png"),
                 dpi=150, bbox_inches="tight")
    print("  rom_sweep.png")

    fig4 = plt.figure(figsize=(12, 8))
    plot_summary(fig4, all_results, F_cable)
    fig4.savefig(os.path.join(OUTPUT_DIR, "summary_dashboard.png"),
                 dpi=150, bbox_inches="tight")
    print("  summary_dashboard.png")

    plt.close("all")
    print("\nDone. All figures saved to:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
