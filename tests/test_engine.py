"""Basic sanity checks for the biomechanics engine."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

import numpy as np
import pytest
from biomek.equipment import EquipmentModel
from biomek.exercises import load_exercises
from biomek.engine import BiomechanicsEngine


@pytest.fixture
def exercises():
    return load_exercises()


@pytest.fixture
def engine_trad():
    return BiomechanicsEngine(EquipmentModel("traditional"))


@pytest.fixture
def engine_dev():
    return BiomechanicsEngine(EquipmentModel("biomek"))


def test_device_wrist_torque_is_zero():
    eq = EquipmentModel("biomek")
    assert eq.wrist_torque(50.0) == 0.0


def test_traditional_wrist_torque_nonzero():
    eq = EquipmentModel("traditional")
    assert eq.wrist_torque(50.0) > 0.0


def test_device_grip_fraction_lower(engine_trad, engine_dev, exercises):
    ex = exercises[0]  # Standard Curl
    angle = np.radians(90)
    act_trad = engine_trad.compute_muscle_activations(50.0, angle, ex)
    act_dev = engine_dev.compute_muscle_activations(50.0, angle, ex)
    assert act_dev["forearm_flexors"] < act_trad["forearm_flexors"]


def test_wrist_stress_lower_for_device(engine_trad, engine_dev, exercises):
    ex = exercises[0]
    angle = np.radians(90)
    st_trad = engine_trad.compute_joint_stress(50.0, angle, ex)
    st_dev = engine_dev.compute_joint_stress(50.0, angle, ex)
    assert st_dev["wrist"] < st_trad["wrist"]


def test_sweep_rom_returns_correct_shape(engine_trad, exercises):
    ex = exercises[0]
    result = engine_trad.sweep_rom(50.0, ex, n_points=20)
    assert len(result["angles_deg"]) == 20
    for m in ex.muscles_involved:
        assert len(result["activations"][m]) == 20


def test_peak_activations_positive(engine_trad, exercises):
    for ex in exercises:
        result = engine_trad.sweep_rom(50.0, ex)
        for m, peak in result["peak_activations"].items():
            assert peak >= 0.0, f"{m} has negative peak activation"
