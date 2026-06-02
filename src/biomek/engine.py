"""Biomechanics engine: computes muscle activations and joint stresses."""

import numpy as np
from .anatomy import muscle_moment_arm, muscle_max_force, JOINT_REF_AREA
from .equipment import EquipmentModel
from .exercises import Exercise


class BiomechanicsEngine:
    """Computes muscle activations and joint stresses for an exercise + equipment combo."""

    def __init__(self, equipment: EquipmentModel):
        self.eq = equipment

    def external_torque(self, f_cable: float, angle_rad: float, exercise: Exercise) -> float:
        """External torque (N·m) about the primary joint from cable force."""
        if exercise.joint == "elbow":
            return f_cable * self.eq.force_distance_from_elbow() * np.sin(angle_rad)
        else:  # shoulder
            return f_cable * self.eq.force_distance_from_shoulder() * np.sin(angle_rad)

    def compute_muscle_activations(
        self, f_cable: float, angle_rad: float, exercise: Exercise
    ) -> dict[str, float]:
        """Returns {muscle_name: activation_%MVC} at a given joint angle."""
        tau_ext = self.external_torque(f_cable, angle_rad, exercise)
        activations = {}

        for muscle in exercise.muscles_involved:
            if muscle == "forearm_flexors":
                grip_force = self.eq.grip_force_fraction() * f_cable
                activations[muscle] = (grip_force / muscle_max_force(muscle)) * 100.0
            else:
                w = exercise.muscle_weights.get(muscle, 0.0)
                ma = muscle_moment_arm(muscle, angle_rad)
                f_muscle = (w * tau_ext) / ma if ma > 0.001 else 0.0
                activations[muscle] = (f_muscle / muscle_max_force(muscle)) * 100.0

        return activations

    def compute_joint_stress(
        self, f_cable: float, angle_rad: float, exercise: Exercise
    ) -> dict[str, float]:
        """Returns {joint_name: stress_index (N/m²)} at a given joint angle."""
        tau_ext = self.external_torque(f_cable, angle_rad, exercise)
        stresses = {}

        # Wrist
        tau_wrist = self.eq.wrist_torque(f_cable)
        grip_force = self.eq.grip_force_fraction() * f_cable
        wrist_force = np.sqrt(grip_force**2 + (tau_wrist / 0.02)**2)
        stresses["wrist"] = wrist_force / JOINT_REF_AREA["wrist"]

        # Elbow
        if exercise.joint == "elbow":
            total_muscle_f = sum(
                (exercise.muscle_weights.get(m, 0.0) * tau_ext)
                / muscle_moment_arm(m, angle_rad)
                for m in exercise.muscles_involved
                if m != "forearm_flexors" and muscle_moment_arm(m, angle_rad) > 0.001
            )
            elbow_force = np.sqrt(total_muscle_f**2 + (f_cable * np.cos(angle_rad))**2)
            stresses["elbow"] = elbow_force / JOINT_REF_AREA["elbow"]
        else:
            stresses["elbow"] = (f_cable * 0.1) / JOINT_REF_AREA["elbow"]

        # Shoulder
        if exercise.joint == "shoulder":
            total_muscle_f = sum(
                (exercise.muscle_weights.get(m, 0.0) * tau_ext)
                / muscle_moment_arm(m, angle_rad)
                for m in exercise.muscles_involved
                if m != "forearm_flexors" and muscle_moment_arm(m, angle_rad) > 0.001
            )
            stresses["shoulder"] = total_muscle_f / JOINT_REF_AREA["shoulder"]

        return stresses

    def sweep_rom(self, f_cable: float, exercise: Exercise, n_points: int = 50) -> dict:
        """
        Run calculations across the full range of motion.

        Returns dict with keys: angles_deg, activations, stresses,
        peak_activations, peak_stresses.
        """
        a_min, a_max = exercise.angle_range_deg
        angles_deg = np.linspace(a_min, a_max, n_points)
        angles_rad = np.radians(angles_deg)

        all_muscles = exercise.muscles_involved
        activations = {m: np.zeros(n_points) for m in all_muscles}

        joint_names = ["wrist", "elbow"]
        if exercise.joint == "shoulder":
            joint_names.append("shoulder")
        stresses = {j: np.zeros(n_points) for j in joint_names}

        for i, a_rad in enumerate(angles_rad):
            act = self.compute_muscle_activations(f_cable, a_rad, exercise)
            for m in all_muscles:
                activations[m][i] = act.get(m, 0.0)

            st = self.compute_joint_stress(f_cable, a_rad, exercise)
            for j in joint_names:
                stresses[j][i] = st.get(j, 0.0)

        return {
            "angles_deg": angles_deg,
            "activations": activations,
            "stresses": stresses,
            "peak_activations": {m: float(np.max(activations[m])) for m in all_muscles},
            "peak_stresses": {j: float(np.max(stresses[j])) for j in joint_names},
        }
