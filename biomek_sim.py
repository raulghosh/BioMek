"""
BioMek Forearm Device — Biomechanical Simulation
=================================================
Compares the BioMek forearm cable attachment against a traditional cable handle
for three exercises: Standard Curl, Reverse Curl, and Lateral Raise.

Outputs:
  1. equipment_schematic.png  — Device diagram
  2. muscle_activation.png    — Peak muscle activation comparison
  3. joint_stress.png         — Wrist/elbow/shoulder stress comparison
  4. rom_sweep.png            — Activation & stress across full ROM

Usage:
  python biomek_sim.py
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import os

# ============================================================
# SECTION 1: Configuration & Constants
# ============================================================

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

F_CABLE = 50.0  # Newtons (~11 lbs), moderate cable weight

# Segment lengths (meters)
UPPER_ARM_LENGTH = 0.30
FOREARM_LENGTH = 0.25
HAND_LENGTH = 0.10
HAND_GRIP_CENTER = 0.05  # mid-palm from wrist

# Device geometry
DEVICE_PAD_FROM_WRIST = 0.02  # pad sits 2 cm above wrist joint

# Muscle parameters: (insertion_dist_from_joint, Fmax, base_moment_arm, moment_arm_variation)
MUSCLE_PARAMS = {
    "biceps":           {"insertion": 0.04, "Fmax": 800,  "ma_base": 0.040, "ma_var": 0.50},
    "brachialis":       {"insertion": 0.03, "Fmax": 1000, "ma_base": 0.030, "ma_var": 0.30},
    "brachioradialis":  {"insertion": 0.20, "Fmax": 200,  "ma_base": 0.050, "ma_var": 0.20},
    "forearm_flexors":  {"insertion": 0.05, "Fmax": 600,  "ma_base": 0.025, "ma_var": 0.10},
    "deltoid_lateral":  {"insertion": 0.15, "Fmax": 1200, "ma_base": 0.020, "ma_var": 2.00},
    "deltoid_anterior": {"insertion": 0.15, "Fmax": 1200, "ma_base": 0.018, "ma_var": 1.50},
    "supraspinatus":    {"insertion": 0.02, "Fmax": 400,  "ma_base": 0.010, "ma_var": 0.80},
}

# Joint stress reference areas (m²) for normalization
JOINT_REF_AREA = {
    "wrist": 0.0006,
    "elbow": 0.0012,
    "shoulder": 0.0020,
}

# Plot colors
COLORS = {
    "biceps": "#e74c3c",
    "brachialis": "#e67e22",
    "brachioradialis": "#f1c40f",
    "forearm_flexors": "#95a5a6",
    "deltoid_lateral": "#3498db",
    "deltoid_anterior": "#2980b9",
    "supraspinatus": "#8e44ad",
}

DEVICE_COLOR = "#2ecc71"
TRAD_COLOR = "#e74c3c"


# ============================================================
# SECTION 2: Anatomy Helper Functions
# ============================================================

def muscle_moment_arm(muscle_name, joint_angle_rad):
    """
    Returns the effective moment arm (meters) of a muscle at a given joint angle.
    Moment arm varies sinusoidally, peaking near 90° of flexion/abduction.

    Parameters
    ----------
    muscle_name : str
    joint_angle_rad : float — joint angle in radians (0 = extended)

    Returns
    -------
    float — moment arm in meters
    """
    p = MUSCLE_PARAMS[muscle_name]
    return p["ma_base"] * (1.0 + p["ma_var"] * np.sin(joint_angle_rad))


def muscle_max_force(muscle_name):
    """Returns the maximum isometric force (N) for a muscle."""
    return MUSCLE_PARAMS[muscle_name]["Fmax"]


# ============================================================
# SECTION 3: Equipment Model
# ============================================================

class EquipmentModel:
    """Models force application for either traditional handle or BioMek device."""

    def __init__(self, mode="traditional"):
        """
        Parameters
        ----------
        mode : str — "traditional" or "biomek"
        """
        assert mode in ("traditional", "biomek"), f"Unknown mode: {mode}"
        self.mode = mode

    def force_distance_from_elbow(self):
        """Distance (m) from elbow to the point where cable force is applied."""
        if self.mode == "traditional":
            return FOREARM_LENGTH + HAND_GRIP_CENTER  # 0.30 m
        else:
            return FOREARM_LENGTH - DEVICE_PAD_FROM_WRIST  # 0.23 m

    def force_distance_from_shoulder(self):
        """Distance (m) from shoulder to force application point."""
        if self.mode == "traditional":
            return UPPER_ARM_LENGTH + FOREARM_LENGTH + HAND_GRIP_CENTER  # 0.65 m
        else:
            return UPPER_ARM_LENGTH + FOREARM_LENGTH - DEVICE_PAD_FROM_WRIST  # 0.53 m

    def grip_force_fraction(self):
        """Fraction of cable force that must be supported by grip."""
        return 1.0 if self.mode == "traditional" else 0.05

    def wrist_torque(self, F_cable):
        """Torque (N·m) at wrist joint from the cable force."""
        if self.mode == "traditional":
            return F_cable * HAND_GRIP_CENTER
        else:
            return 0.0  # force applied proximal to wrist


# ============================================================
# SECTION 4: Exercise Definitions
# ============================================================

class Exercise:
    """Stores parameters for one exercise type."""

    def __init__(self, name, joint, angle_range_deg, muscle_weights, muscles_involved):
        """
        Parameters
        ----------
        name : str — e.g. "Standard Curl"
        joint : str — "elbow" or "shoulder"
        angle_range_deg : tuple — (min_deg, max_deg) for ROM sweep
        muscle_weights : dict — {muscle_name: fractional_contribution} summing to ~1.0
        muscles_involved : list — muscle names active in this exercise
        """
        self.name = name
        self.joint = joint
        self.angle_range_deg = angle_range_deg
        self.muscle_weights = muscle_weights
        self.muscles_involved = muscles_involved


# Define the three exercises
EXERCISES = [
    Exercise(
        name="Standard Curl",
        joint="elbow",
        angle_range_deg=(10, 150),
        muscle_weights={"biceps": 0.45, "brachialis": 0.40, "brachioradialis": 0.15},
        muscles_involved=["biceps", "brachialis", "brachioradialis", "forearm_flexors"],
    ),
    Exercise(
        name="Reverse Curl",
        joint="elbow",
        angle_range_deg=(10, 150),
        muscle_weights={"biceps": 0.25, "brachialis": 0.35, "brachioradialis": 0.40},
        muscles_involved=["biceps", "brachialis", "brachioradialis", "forearm_flexors"],
    ),
    Exercise(
        name="Lateral Raise",
        joint="shoulder",
        angle_range_deg=(5, 90),
        muscle_weights={"deltoid_lateral": 0.60, "deltoid_anterior": 0.25, "supraspinatus": 0.15},
        muscles_involved=["deltoid_lateral", "deltoid_anterior", "supraspinatus", "forearm_flexors"],
    ),
]


# ============================================================
# SECTION 5: Biomechanics Engine
# ============================================================

class BiomechanicsEngine:
    """Computes muscle activations and joint stresses for an exercise + equipment combo."""

    def __init__(self, equipment: EquipmentModel):
        self.eq = equipment

    def external_torque(self, F_cable, angle_rad, exercise: Exercise):
        """
        Compute the external torque (N·m) about the primary joint.

        For curls (elbow): τ = F × L_force × sin(θ_elbow)
        For raises (shoulder): τ = F × L_force × cos(θ_shoulder)
            (cos because at 0° abduction gravity torque is max, at 90° cable torque is max —
             but for cable lateral raise from a low pulley, torque ∝ sin(θ) actually)
        """
        if exercise.joint == "elbow":
            L = self.eq.force_distance_from_elbow()
            # Cable from low pulley: force is roughly vertical
            # Forearm angle from vertical = (π - θ_elbow) when upper arm hangs
            # Perpendicular component of cable force on forearm = sin(θ_elbow)
            return F_cable * L * np.sin(angle_rad)
        else:  # shoulder
            L = self.eq.force_distance_from_shoulder()
            # Cable from side low pulley: effective torque increases with abduction angle
            return F_cable * L * np.sin(angle_rad)

    def compute_muscle_activations(self, F_cable, angle_rad, exercise: Exercise):
        """
        Returns dict of {muscle_name: activation_%MVC} at a given joint angle.

        Steps:
        1. Compute external torque about joint
        2. Distribute torque among muscles per their weight fractions
        3. Compute each muscle's required force = (weight × torque) / moment_arm
        4. Activation = force / Fmax × 100
        """
        tau_ext = self.external_torque(F_cable, angle_rad, exercise)
        activations = {}

        for muscle in exercise.muscles_involved:
            if muscle == "forearm_flexors":
                # Grip activation depends on equipment
                grip_force = self.eq.grip_force_fraction() * F_cable
                activations[muscle] = (grip_force / muscle_max_force(muscle)) * 100.0
            else:
                w = exercise.muscle_weights.get(muscle, 0.0)
                ma = muscle_moment_arm(muscle, angle_rad)
                if ma > 0.001:
                    F_muscle = (w * tau_ext) / ma
                else:
                    F_muscle = 0.0
                activations[muscle] = (F_muscle / muscle_max_force(muscle)) * 100.0

        return activations

    def compute_joint_stress(self, F_cable, angle_rad, exercise: Exercise):
        """
        Returns dict of {joint_name: stress_index} (N/m² normalized).

        Stress components:
        - Wrist: from grip torque (bypassed by device)
        - Elbow: from muscle reaction forces + cable force
        - Shoulder: from total arm weight + cable (for raises)
        """
        tau_ext = self.external_torque(F_cable, angle_rad, exercise)
        stresses = {}

        # --- Wrist stress ---
        tau_wrist = self.eq.wrist_torque(F_cable)
        grip_force = self.eq.grip_force_fraction() * F_cable
        # Total wrist load = grip force + torque-induced shear
        wrist_force = np.sqrt(grip_force**2 + (tau_wrist / 0.02)**2)  # torque / wrist width
        stresses["wrist"] = wrist_force / JOINT_REF_AREA["wrist"]

        # --- Elbow stress ---
        if exercise.joint == "elbow":
            # Sum of muscle forces crossing the elbow
            total_muscle_F = 0.0
            for muscle in exercise.muscles_involved:
                if muscle == "forearm_flexors":
                    continue
                w = exercise.muscle_weights.get(muscle, 0.0)
                ma = muscle_moment_arm(muscle, angle_rad)
                if ma > 0.001:
                    total_muscle_F += (w * tau_ext) / ma

            # Joint reaction ≈ muscle force - cable component along bone
            # Simplified: compressive = muscle_force, shear = cable × sin(angle)
            F_compress = total_muscle_F
            F_shear = F_cable * np.cos(angle_rad)
            elbow_force = np.sqrt(F_compress**2 + F_shear**2)
            stresses["elbow"] = elbow_force / JOINT_REF_AREA["elbow"]
        else:
            # For lateral raise, elbow stress is minimal (arm is relatively straight)
            stresses["elbow"] = (F_cable * 0.1) / JOINT_REF_AREA["elbow"]

        # --- Shoulder stress (for lateral raise) ---
        if exercise.joint == "shoulder":
            total_muscle_F = 0.0
            for muscle in exercise.muscles_involved:
                if muscle == "forearm_flexors":
                    continue
                w = exercise.muscle_weights.get(muscle, 0.0)
                ma = muscle_moment_arm(muscle, angle_rad)
                if ma > 0.001:
                    total_muscle_F += (w * tau_ext) / ma
            stresses["shoulder"] = total_muscle_F / JOINT_REF_AREA["shoulder"]

        return stresses

    def sweep_rom(self, F_cable, exercise: Exercise, n_points=50):
        """
        Run calculations across the full range of motion.

        Returns
        -------
        dict with keys:
            "angles_deg": array of joint angles
            "activations": {muscle: array of %MVC}
            "stresses": {joint: array of stress values}
            "peak_activations": {muscle: peak %MVC across ROM}
            "peak_stresses": {joint: peak stress across ROM}
        """
        a_min, a_max = exercise.angle_range_deg
        angles_deg = np.linspace(a_min, a_max, n_points)
        angles_rad = np.radians(angles_deg)

        # Initialize storage
        all_muscles = exercise.muscles_involved
        activations = {m: np.zeros(n_points) for m in all_muscles}

        # Determine which joints to track
        joint_names = ["wrist", "elbow"]
        if exercise.joint == "shoulder":
            joint_names.append("shoulder")
        stresses = {j: np.zeros(n_points) for j in joint_names}

        # Sweep
        for i, (a_deg, a_rad) in enumerate(zip(angles_deg, angles_rad)):
            act = self.compute_muscle_activations(F_cable, a_rad, exercise)
            for m in all_muscles:
                activations[m][i] = act.get(m, 0.0)

            st = self.compute_joint_stress(F_cable, a_rad, exercise)
            for j in joint_names:
                stresses[j][i] = st.get(j, 0.0)

        # Peak values
        peak_act = {m: float(np.max(activations[m])) for m in all_muscles}
        peak_st = {j: float(np.max(stresses[j])) for j in joint_names}

        return {
            "angles_deg": angles_deg,
            "activations": activations,
            "stresses": stresses,
            "peak_activations": peak_act,
            "peak_stresses": peak_st,
        }


# ============================================================
# SECTION 6: Visualization
# ============================================================

def plot_equipment_schematic(fig):
    """Draw a top-down schematic of the BioMek device on the given figure."""
    ax = fig.add_subplot(111)
    ax.set_xlim(-2, 12)
    ax.set_ylim(-2, 8)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("BioMek Forearm Device — Top View", fontsize=16, fontweight="bold", pad=20)

    # Main rectangle (PVC frame)
    rect = mpatches.FancyBboxPatch(
        (1, 1), 8, 5, boxstyle="round,pad=0.2",
        facecolor="none", edgecolor="#2c3e50", linewidth=3
    )
    ax.add_patch(rect)

    # Padded arm (bottom long side) — with pool-noodle effect
    padding = mpatches.FancyBboxPatch(
        (1, 0.3), 8, 1.4, boxstyle="round,pad=0.3",
        facecolor="#a8d8ea", edgecolor="#3498db", linewidth=2, alpha=0.7
    )
    ax.add_patch(padding)
    ax.text(5, 1.0, 'PADDED ARM (on forearm bone)', ha='center', va='center',
            fontsize=9, fontweight='bold', color='#2c3e50')

    # Palm arm (top long side)
    palm = mpatches.FancyBboxPatch(
        (1, 5.3), 8, 0.7, boxstyle="round,pad=0.1",
        facecolor="#fadbd8", edgecolor="#e74c3c", linewidth=2, alpha=0.7
    )
    ax.add_patch(palm)
    ax.text(5, 5.65, 'PALM REST ARM (stabilizer)', ha='center', va='center',
            fontsize=9, fontweight='bold', color='#922b21')

    # Short connecting arms (left and right)
    for x in [1.2, 8.8]:
        ax.plot([x, x], [1.7, 5.3], color='#7f8c8d', linewidth=6, solid_capstyle='round')

    # Dimension annotations
    ax.annotate('', xy=(9.5, 1), xytext=(9.5, 6),
                arrowprops=dict(arrowstyle='<->', color='#2c3e50', lw=1.5))
    ax.text(10.2, 3.5, '6"', fontsize=12, ha='center', va='center', color='#2c3e50')

    ax.annotate('', xy=(1, 7), xytext=(9, 7),
                arrowprops=dict(arrowstyle='<->', color='#2c3e50', lw=1.5))
    ax.text(5, 7.4, '6" (long arms)', fontsize=10, ha='center', color='#2c3e50')

    ax.annotate('', xy=(0.3, 1.7), xytext=(0.3, 5.3),
                arrowprops=dict(arrowstyle='<->', color='#7f8c8d', lw=1.2))
    ax.text(-0.5, 3.5, '3"', fontsize=10, ha='center', va='center', color='#7f8c8d')

    # Harness loop
    harness_x = [0.2, -0.5, -0.5, 0.2]
    harness_y = [1.0, 0.5, -0.5, -1.0]
    ax.plot(harness_x, harness_y, color='#27ae60', linewidth=3, linestyle='--')
    ax.plot([9.8, 10.5, 10.5, 9.8], [1.0, 0.5, -0.5, -1.0],
            color='#27ae60', linewidth=3, linestyle='--')
    ax.text(5, -1.2, '⟵ HARNESS LOOP (clips to cable carabiner) ⟶',
            ha='center', fontsize=10, color='#27ae60', fontweight='bold')

    # Legend
    ax.text(5, -1.9, 'Blue padding = rests on forearm bone  |  Red = palm rest  |  Green = harness to cable',
            ha='center', fontsize=8, color='#7f8c8d', style='italic')


def plot_muscle_activation_comparison(fig, all_results):
    """
    Bar chart comparing peak muscle activation across exercises.
    all_results: list of (exercise, results_device, results_trad)
    """
    n_ex = len(all_results)
    gs = GridSpec(1, n_ex, figure=fig, wspace=0.35)

    for idx, (exercise, res_dev, res_trad) in enumerate(all_results):
        ax = fig.add_subplot(gs[0, idx])

        muscles = [m for m in exercise.muscles_involved if m != "forearm_flexors"]
        muscles.append("forearm_flexors")  # always last

        dev_vals = [res_dev["peak_activations"].get(m, 0) for m in muscles]
        trad_vals = [res_trad["peak_activations"].get(m, 0) for m in muscles]

        x = np.arange(len(muscles))
        width = 0.35

        bars_trad = ax.bar(x - width/2, trad_vals, width, label="Traditional",
                           color=[COLORS.get(m, "#bdc3c7") for m in muscles],
                           edgecolor="black", linewidth=0.5, alpha=0.5)
        bars_dev = ax.bar(x + width/2, dev_vals, width, label="BioMek Device",
                          color=[COLORS.get(m, "#bdc3c7") for m in muscles],
                          edgecolor="black", linewidth=1.2)

        # Add value labels on top of bars
        for bar in bars_trad:
            h = bar.get_height()
            if h > 1:
                ax.text(bar.get_x() + bar.get_width()/2, h + 0.5,
                        f'{h:.0f}%', ha='center', va='bottom', fontsize=7, color='#666')
        for bar in bars_dev:
            h = bar.get_height()
            if h > 1:
                ax.text(bar.get_x() + bar.get_width()/2, h + 0.5,
                        f'{h:.0f}%', ha='center', va='bottom', fontsize=7, fontweight='bold')

        labels = [m.replace("_", "\n") for m in muscles]
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=7)
        ax.set_ylabel("Peak Activation (% MVC)" if idx == 0 else "")
        ax.set_title(exercise.name, fontsize=12, fontweight="bold")
        ax.set_ylim(0, max(max(dev_vals), max(trad_vals)) * 1.25 + 5)

        if idx == 0:
            # Custom legend
            legend_handles = [
                mpatches.Patch(facecolor='gray', alpha=0.5, edgecolor='black', linewidth=0.5, label='Traditional'),
                mpatches.Patch(facecolor='gray', alpha=1.0, edgecolor='black', linewidth=1.2, label='BioMek Device'),
            ]
            ax.legend(handles=legend_handles, fontsize=8, loc='upper left')


def plot_joint_stress_comparison(fig, all_results):
    """Grouped bar chart comparing joint stresses: device vs traditional for all exercises."""
    ax = fig.add_subplot(111)

    exercises_names = []
    joint_names_ordered = ["wrist", "elbow", "shoulder"]
    # Collect data
    data_trad = {j: [] for j in joint_names_ordered}
    data_dev = {j: [] for j in joint_names_ordered}

    for exercise, res_dev, res_trad in all_results:
        exercises_names.append(exercise.name)
        for j in joint_names_ordered:
            # Convert to kPa for readability
            data_trad[j].append(res_trad["peak_stresses"].get(j, 0) / 1000)
            data_dev[j].append(res_dev["peak_stresses"].get(j, 0) / 1000)

    x = np.arange(len(exercises_names))
    n_joints = len(joint_names_ordered)
    total_width = 0.7
    bar_width = total_width / (n_joints * 2)

    joint_colors = {"wrist": "#e74c3c", "elbow": "#f39c12", "shoulder": "#3498db"}

    for j_idx, jname in enumerate(joint_names_ordered):
        offset_trad = -total_width/2 + j_idx * 2 * bar_width + bar_width * 0.5
        offset_dev = offset_trad + bar_width

        vals_trad = data_trad[jname]
        vals_dev = data_dev[jname]

        ax.bar(x + offset_trad, vals_trad, bar_width,
               color=joint_colors[jname], alpha=0.4, edgecolor='black', linewidth=0.5,
               label=f'{jname.title()} (Trad)' if True else '')
        ax.bar(x + offset_dev, vals_dev, bar_width,
               color=joint_colors[jname], alpha=1.0, edgecolor='black', linewidth=1.0,
               label=f'{jname.title()} (BioMek)')

        # Add percentage reduction annotations
        for i in range(len(exercises_names)):
            if vals_trad[i] > 0.1:
                reduction = (1 - vals_dev[i] / vals_trad[i]) * 100
                max_val = max(vals_trad[i], vals_dev[i])
                if reduction > 5:
                    ax.text(x[i] + offset_dev, max_val + 2,
                            f'-{reduction:.0f}%', ha='center', va='bottom',
                            fontsize=7, color=joint_colors[jname], fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels(exercises_names, fontsize=11)
    ax.set_ylabel("Peak Joint Stress (kPa)", fontsize=11)
    ax.set_title("Joint Stress Comparison: BioMek Device vs Traditional Handle",
                 fontsize=14, fontweight="bold")
    ax.legend(fontsize=8, ncol=3, loc='upper right')
    ax.grid(axis='y', alpha=0.3)


def plot_rom_sweep(fig, all_results):
    """Line plots: muscle activation and joint stress across the ROM for each exercise."""
    n_ex = len(all_results)
    gs = GridSpec(n_ex, 2, figure=fig, hspace=0.5, wspace=0.3)

    for idx, (exercise, res_dev, res_trad) in enumerate(all_results):
        angles = res_dev["angles_deg"]

        # --- Left column: muscle activation ---
        ax1 = fig.add_subplot(gs[idx, 0])
        for muscle in exercise.muscles_involved:
            color = COLORS.get(muscle, "#bdc3c7")
            label = muscle.replace("_", " ").title()
            ax1.plot(angles, res_trad["activations"][muscle], '--', color=color,
                     alpha=0.5, linewidth=1.5)
            ax1.plot(angles, res_dev["activations"][muscle], '-', color=color,
                     linewidth=2, label=label)

        ax1.set_xlabel(f'{exercise.joint.title()} Angle (°)', fontsize=9)
        ax1.set_ylabel('Activation (% MVC)', fontsize=9)
        ax1.set_title(f'{exercise.name} — Muscle Activation', fontsize=11, fontweight='bold')
        ax1.legend(fontsize=7, loc='upper left')
        ax1.grid(alpha=0.3)

        # Add legend note for line styles
        if idx == 0:
            ax1.text(0.98, 0.02, 'Solid = BioMek, Dashed = Traditional',
                     transform=ax1.transAxes, fontsize=7, ha='right', va='bottom',
                     style='italic', color='#666')

        # --- Right column: joint stress ---
        ax2 = fig.add_subplot(gs[idx, 1])
        joint_colors = {"wrist": "#e74c3c", "elbow": "#f39c12", "shoulder": "#3498db"}

        for jname in res_dev["stresses"]:
            color = joint_colors.get(jname, "#bdc3c7")
            label = jname.title()
            trad_kpa = res_trad["stresses"][jname] / 1000
            dev_kpa = res_dev["stresses"][jname] / 1000
            ax2.plot(angles, trad_kpa, '--', color=color, alpha=0.5, linewidth=1.5)
            ax2.plot(angles, dev_kpa, '-', color=color, linewidth=2, label=label)

        ax2.set_xlabel(f'{exercise.joint.title()} Angle (°)', fontsize=9)
        ax2.set_ylabel('Joint Stress (kPa)', fontsize=9)
        ax2.set_title(f'{exercise.name} — Joint Stress', fontsize=11, fontweight='bold')
        ax2.legend(fontsize=7, loc='upper left')
        ax2.grid(alpha=0.3)

        if idx == 0:
            ax2.text(0.98, 0.02, 'Solid = BioMek, Dashed = Traditional',
                     transform=ax2.transAxes, fontsize=7, ha='right', va='bottom',
                     style='italic', color='#666')


def plot_summary_dashboard(fig, all_results):
    """
    Single-page summary showing stress reduction percentages and key takeaways.
    """
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)

    ax.text(5, 9.5, "BioMek Device — Impact Summary",
            fontsize=18, fontweight="bold", ha="center", va="top", color="#2c3e50")
    ax.text(5, 9.0, f"Cable load: {F_CABLE:.0f} N ({F_CABLE * 0.2248:.1f} lbs)",
            fontsize=11, ha="center", va="top", color="#7f8c8d")

    y = 8.2
    for exercise, res_dev, res_trad in all_results:
        ax.text(0.5, y, exercise.name, fontsize=14, fontweight="bold", color="#2c3e50")
        y -= 0.5

        # Wrist stress reduction
        ws_trad = res_trad["peak_stresses"].get("wrist", 0)
        ws_dev = res_dev["peak_stresses"].get("wrist", 0)
        ws_red = (1 - ws_dev / ws_trad) * 100 if ws_trad > 0 else 0

        # Elbow stress reduction
        es_trad = res_trad["peak_stresses"].get("elbow", 0)
        es_dev = res_dev["peak_stresses"].get("elbow", 0)
        es_red = (1 - es_dev / es_trad) * 100 if es_trad > 0 else 0

        # Grip reduction
        gf_trad = res_trad["peak_activations"].get("forearm_flexors", 0)
        gf_dev = res_dev["peak_activations"].get("forearm_flexors", 0)
        gf_red = (1 - gf_dev / gf_trad) * 100 if gf_trad > 0 else 0

        ax.text(1.0, y, f"Wrist stress: -{ws_red:.0f}%", fontsize=11, color="#e74c3c")
        ax.text(4.0, y, f"Elbow stress: -{es_red:.0f}%", fontsize=11, color="#f39c12")
        ax.text(7.0, y, f"Grip demand: -{gf_red:.0f}%", fontsize=11, color="#95a5a6")
        y -= 0.5

        # Primary muscle comparison
        primary_muscles = [m for m in exercise.muscles_involved if m != "forearm_flexors"]
        for m in primary_muscles:
            peak_dev = res_dev["peak_activations"].get(m, 0)
            peak_trad = res_trad["peak_activations"].get(m, 0)
            ratio = peak_dev / peak_trad * 100 if peak_trad > 0 else 0
            mname = m.replace("_", " ").title()
            ax.text(1.0, y, f"  {mname}: {peak_dev:.1f}% MVC (= {ratio:.0f}% of traditional)",
                    fontsize=9, color="#555")
            y -= 0.35
        y -= 0.3

    # Takeaway
    ax.text(0.5, y, "Key Takeaway:", fontsize=12, fontweight="bold", color="#27ae60")
    y -= 0.45
    ax.text(0.5, y,
            "The BioMek device virtually eliminates wrist stress and grip demand.",
            fontsize=10, color="#2c3e50")
    y -= 0.35
    ax.text(0.5, y,
            "Primary muscle activation is ~77% of traditional per unit cable load.",
            fontsize=10, color="#2c3e50")
    y -= 0.35
    ax.text(0.5, y,
            "Increase cable weight ~25-30% to match the same muscle stimulus with zero wrist strain.",
            fontsize=10, color="#2c3e50")


# ============================================================
# SECTION 7: Main — Run Simulation
# ============================================================

def main():
    print("=" * 60)
    print("BioMek Forearm Device — Biomechanical Simulation")
    print("=" * 60)
    print(f"Cable load: {F_CABLE:.0f} N ({F_CABLE * 0.2248:.1f} lbs)\n")

    # Create equipment models
    eq_trad = EquipmentModel("traditional")
    eq_dev = EquipmentModel("biomek")

    engine_trad = BiomechanicsEngine(eq_trad)
    engine_dev = BiomechanicsEngine(eq_dev)

    # Run all exercises
    all_results = []  # list of (exercise, results_device, results_traditional)

    for ex in EXERCISES:
        print(f"--- {ex.name} ---")
        res_trad = engine_trad.sweep_rom(F_CABLE, ex)
        res_dev = engine_dev.sweep_rom(F_CABLE, ex)
        all_results.append((ex, res_dev, res_trad))

        # Print summary
        print(f"  Peak muscle activations (% MVC):")
        for m in ex.muscles_involved:
            pt = res_trad["peak_activations"].get(m, 0)
            pd = res_dev["peak_activations"].get(m, 0)
            mname = m.replace("_", " ").title()
            print(f"    {mname:22s}  Trad: {pt:6.1f}%  Device: {pd:6.1f}%")

        print(f"  Peak joint stresses (kPa):")
        for j in res_trad["peak_stresses"]:
            st = res_trad["peak_stresses"][j] / 1000
            sd = res_dev["peak_stresses"][j] / 1000
            reduction = (1 - sd / st) * 100 if st > 0 else 0
            print(f"    {j.title():12s}  Trad: {st:8.1f}  Device: {sd:8.1f}  (↓{reduction:.0f}%)")
        print()

    # ---- Generate figures ----
    print("Generating visualizations...")

    # Figure 1: Equipment schematic
    fig1 = plt.figure(figsize=(12, 7))
    plot_equipment_schematic(fig1)
    fig1.savefig(os.path.join(OUTPUT_DIR, "equipment_schematic.png"), dpi=150, bbox_inches="tight")
    print("  Saved equipment_schematic.png")

    # Figure 2: Muscle activation comparison
    fig2 = plt.figure(figsize=(16, 6))
    fig2.suptitle("Peak Muscle Activation: BioMek Device vs Traditional Handle",
                  fontsize=14, fontweight="bold", y=1.02)
    plot_muscle_activation_comparison(fig2, all_results)
    fig2.savefig(os.path.join(OUTPUT_DIR, "muscle_activation.png"), dpi=150, bbox_inches="tight")
    print("  Saved muscle_activation.png")

    # Figure 3: Joint stress comparison
    fig3 = plt.figure(figsize=(12, 6))
    plot_joint_stress_comparison(fig3, all_results)
    fig3.savefig(os.path.join(OUTPUT_DIR, "joint_stress.png"), dpi=150, bbox_inches="tight")
    print("  Saved joint_stress.png")

    # Figure 4: ROM sweep
    fig4 = plt.figure(figsize=(14, 12))
    fig4.suptitle("Range of Motion Analysis: BioMek vs Traditional",
                  fontsize=14, fontweight="bold")
    plot_rom_sweep(fig4, all_results)
    fig4.savefig(os.path.join(OUTPUT_DIR, "rom_sweep.png"), dpi=150, bbox_inches="tight")
    print("  Saved rom_sweep.png")

    # Figure 5: Summary dashboard
    fig5 = plt.figure(figsize=(12, 8))
    plot_summary_dashboard(fig5, all_results)
    fig5.savefig(os.path.join(OUTPUT_DIR, "summary_dashboard.png"), dpi=150, bbox_inches="tight")
    print("  Saved summary_dashboard.png")

    plt.close("all")
    print("\nSimulation complete. All figures saved.")


if __name__ == "__main__":
    main()
