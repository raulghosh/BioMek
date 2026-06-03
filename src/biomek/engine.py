"""
Static-optimization biomechanics engine.
Minimizes sum(a_i²) subject to torque balance — same approach as biomek_sim.py.
"""

import numpy as np
from .anatomy import JOINT_REF_AREA, GRIP_FMAX
from .equipment import EquipmentModel
from .exercises import Exercise


def _solve_static_optimization(tau_required: float,
                                moment_arms_at_angle: dict,
                                muscle_db: dict,
                                muscle_list: list) -> tuple[dict, dict]:
    """
    Analytical SLSQP-equivalent for sum(a²) minimization.
    Uses Lagrange multipliers + iterative clamping for box constraints.
    """
    n = len(muscle_list)
    if n == 0:
        return {}, {}

    Fmax     = np.array([muscle_db[m]["max_isometric_force"] for m in muscle_list])
    ma       = np.array([moment_arms_at_angle.get(m, 0.0) for m in muscle_list])
    cos_penn = np.cos(np.array([muscle_db[m]["pennation_angle"] for m in muscle_list]))

    # Torque capacity coefficient for each muscle
    c = Fmax * cos_penn * ma

    # Only activate muscles that can contribute in the required direction
    active_mask = c > 1e-6 if tau_required >= 0 else c < -1e-6

    if not np.any(active_mask):
        return {m: 0.0 for m in muscle_list}, {m: 0.0 for m in muscle_list}

    c_act = c[active_mask]
    sum_c2 = np.sum(c_act ** 2)
    if sum_c2 < 1e-12:
        return {m: 0.0 for m in muscle_list}, {m: 0.0 for m in muscle_list}

    a_all = np.zeros(n)
    a_all[active_mask] = (2.0 * tau_required / sum_c2) * c_act / 2.0

    # Iterative box-constraint clamping
    for _ in range(6):
        clamped_lo = a_all < 0
        clamped_hi = a_all > 1
        a_all[clamped_lo] = 0.0
        a_all[clamped_hi] = 1.0

        tau_deficit = tau_required - np.sum(a_all * c)
        if abs(tau_deficit) < 1e-6:
            break

        free = ~clamped_lo & ~clamped_hi & active_mask
        c_free = c[free]
        sc2f = np.sum(c_free ** 2)
        if sc2f < 1e-12:
            break
        a_all[free] += (2.0 * tau_deficit / sc2f) * c_free / 2.0

    a_all = np.clip(a_all, 0.0, 1.0)

    acts   = {m: float(a_all[i]) for i, m in enumerate(muscle_list)}
    forces = {m: float(a_all[i] * Fmax[i] * cos_penn[i]) for i, m in enumerate(muscle_list)}
    return acts, forces


class BiomechanicsEngine:

    def __init__(self, equipment: EquipmentModel):
        self.eq = equipment

    def run_simulation(self, exercise: Exercise, f_cable: float,
                       n_points: int = 60) -> dict:
        """
        Sweep the full ROM, run static optimization at each angle.

        Returns a dict with:
          angles_deg, activations, grip_activation, forces,
          wrist_stress, elbow_stress, shoulder_stress,
          peak_activations, peak_wrist_stress, peak_elbow_stress, peak_shoulder_stress
        """
        a_min, a_max = exercise.angle_range_deg
        angles_deg = np.linspace(a_min, a_max, n_points)
        angles_rad = np.radians(angles_deg)

        # All moment arms across ROM
        all_ma = exercise.moment_arm_fn(angles_rad)

        L = (self.eq.elbow_force_distance() if exercise.joint == "elbow"
             else self.eq.shoulder_force_distance())

        activations    = {m: np.zeros(n_points) for m in exercise.muscles}
        forces         = {m: np.zeros(n_points) for m in exercise.muscles}
        grip_act       = np.zeros(n_points)
        wrist_stress   = np.zeros(n_points)
        elbow_stress   = np.zeros(n_points)
        shoulder_stress = np.zeros(n_points)

        for i, (a_deg, a_rad) in enumerate(zip(angles_deg, angles_rad)):
            tau_ext = f_cable * L * np.sin(a_rad)
            ma_i    = {m: float(all_ma[m][i]) for m in exercise.muscles}

            acts, frc = _solve_static_optimization(
                tau_ext, ma_i, exercise.muscle_db, exercise.muscles)

            for m in exercise.muscles:
                activations[m][i] = acts.get(m, 0.0) * 100.0   # → %MVC
                forces[m][i]      = frc.get(m, 0.0)

            # Grip
            grip_force = self.eq.grip_fraction() * f_cable
            grip_act[i] = (grip_force / exercise.grip_fmax) * 100.0

            # Wrist stress
            tau_w = self.eq.wrist_torque(f_cable)
            wf = np.sqrt(grip_force**2 + (tau_w / 0.02)**2)
            wrist_stress[i] = wf / JOINT_REF_AREA["wrist"]

            # Elbow stress
            total_mf = sum(frc.values())
            if exercise.joint == "elbow":
                ef = np.sqrt(total_mf**2 + (f_cable * np.cos(a_rad))**2)
                elbow_stress[i] = ef / JOINT_REF_AREA["elbow"]
            else:
                elbow_stress[i] = (f_cable * 0.1) / JOINT_REF_AREA["elbow"]

            # Shoulder stress
            if exercise.joint == "shoulder":
                shoulder_stress[i] = total_mf / JOINT_REF_AREA["shoulder"]

        peak_act = {m: float(np.max(activations[m])) for m in exercise.muscles}
        peak_act["grip"] = float(np.max(grip_act))

        return {
            "exercise":       exercise.name,
            "equipment":      self.eq.label,
            "angles_deg":     angles_deg,
            "activations":    activations,
            "grip_activation": grip_act,
            "forces":         forces,
            "wrist_stress":   wrist_stress,
            "elbow_stress":   elbow_stress,
            "shoulder_stress": shoulder_stress,
            "peak_activations":      peak_act,
            "peak_wrist_stress":     float(np.max(wrist_stress)),
            "peak_elbow_stress":     float(np.max(elbow_stress)),
            "peak_shoulder_stress":  float(np.max(shoulder_stress)),
        }
