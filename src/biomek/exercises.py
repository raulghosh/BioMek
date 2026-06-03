"""Exercise definitions loaded from config."""

from dataclasses import dataclass, field
from typing import Callable
from .anatomy import (load_config, ELBOW_MUSCLES, SHOULDER_MUSCLES,
                       elbow_moment_arms, shoulder_moment_arms,
                       FLEXORS, EXTENSORS, ABDUCTORS)


@dataclass
class Exercise:
    name: str
    joint: str                       # "elbow" or "shoulder"
    angle_range_deg: tuple           # (min_deg, max_deg)
    muscles: list                    # ordered list of muscle names
    moment_arm_fn: Callable          # elbow_moment_arms or shoulder_moment_arms
    muscle_db: dict                  # ELBOW_MUSCLES or SHOULDER_MUSCLES
    grip_fmax: float = 600.0


def load_exercises(cfg: dict | None = None) -> list[Exercise]:
    """Build Exercise objects from config."""
    if cfg is None:
        cfg = load_config()

    exercises = []
    for key, ex_cfg in cfg["exercises"].items():
        joint = ex_cfg["joint"]
        if joint == "elbow":
            moment_fn = elbow_moment_arms
            muscle_db = ELBOW_MUSCLES
        else:
            moment_fn = shoulder_moment_arms
            muscle_db = SHOULDER_MUSCLES

        exercises.append(Exercise(
            name=ex_cfg["name"],
            joint=joint,
            angle_range_deg=tuple(ex_cfg["angle_range_deg"]),
            muscles=list(ex_cfg["muscles"]),
            moment_arm_fn=moment_fn,
            muscle_db=muscle_db,
            grip_fmax=cfg.get("grip_fmax", 600.0),
        ))
    return exercises
