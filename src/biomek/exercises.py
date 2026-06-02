"""Exercise definitions loaded from config."""

from dataclasses import dataclass, field
from .anatomy import load_config


@dataclass
class Exercise:
    name: str
    joint: str                          # "elbow" or "shoulder"
    angle_range_deg: tuple              # (min_deg, max_deg)
    muscle_weights: dict                # {muscle: fraction}, sums to 1.0
    muscles_involved: list = field(default_factory=list)


def load_exercises(cfg: dict | None = None) -> list[Exercise]:
    """Build Exercise objects from config. Loads default config if none provided."""
    if cfg is None:
        cfg = load_config()
    exercises = []
    for key, ex_cfg in cfg["exercises"].items():
        exercises.append(Exercise(
            name=ex_cfg["name"],
            joint=ex_cfg["joint"],
            angle_range_deg=tuple(ex_cfg["angle_range_deg"]),
            muscle_weights=dict(ex_cfg["muscle_weights"]),
            muscles_involved=list(ex_cfg["muscles_involved"]),
        ))
    return exercises
