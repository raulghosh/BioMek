"""Exercise definitions loaded from config."""

from dataclasses import dataclass, field
from typing import Callable
from .anatomy import (load_config, MUSCLE_DB,
                      elbow_moment_arms, shoulder_moment_arms,
                      shoulder_flexion_moment_arms, shoulder_extension_moment_arms,
                      FLEXORS, EXTENSORS, ABDUCTORS)


# Registry mapping a movement name to its moment-arm function
MOMENT_ARM_FNS: dict[str, Callable] = {
    "elbow":              elbow_moment_arms,
    "shoulder_abduction": shoulder_moment_arms,
    "shoulder_flexion":   shoulder_flexion_moment_arms,
    "shoulder_extension": shoulder_extension_moment_arms,
}


def _default_movement(joint: str) -> str:
    return "elbow" if joint == "elbow" else "shoulder_abduction"


@dataclass
class Exercise:
    name: str
    joint: str                       # "elbow" or "shoulder"
    angle_range_deg: tuple           # (min_deg, max_deg)
    muscles: list                    # ordered list of muscle names
    moment_arm_fn: Callable          # selected from MOMENT_ARM_FNS
    muscle_db: dict                  # merged MUSCLE_DB
    grip_fmax: float = 600.0
    grip_pattern: str = "neutral"    # "supinated" | "pronated" | "neutral"
    direction: int = 1               # +1 flexion/abduction, -1 extension

    @property
    def muscles_involved(self) -> list:
        return self.muscles


def load_exercises(cfg: dict | None = None) -> list[Exercise]:
    """Build Exercise objects from config."""
    if cfg is None:
        cfg = load_config()

    exercises = []
    for key, ex_cfg in cfg["exercises"].items():
        joint    = ex_cfg["joint"]
        movement = ex_cfg.get("movement", _default_movement(joint))

        exercises.append(Exercise(
            name=ex_cfg["name"],
            joint=joint,
            angle_range_deg=tuple(ex_cfg["angle_range_deg"]),
            muscles=list(ex_cfg["muscles"]),
            moment_arm_fn=MOMENT_ARM_FNS[movement],
            muscle_db=MUSCLE_DB,
            grip_fmax=cfg.get("grip_fmax", 600.0),
            grip_pattern=ex_cfg.get("grip_pattern", "neutral"),
            direction=int(ex_cfg.get("direction", 1)),
        ))
    return exercises
