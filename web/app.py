"""
BioMek Web App — Flask backend.
Serves the UI and exposes /api/simulate for live simulation results.

Run:
    cd web
    python app.py
"""

import sys
from pathlib import Path

# Allow imports from src/
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from flask import Flask, render_template, request, jsonify
import numpy as np

from biomek.anatomy import load_config, MUSCLE_PARAMS
from biomek.equipment import EquipmentModel
from biomek.exercises import Exercise
from biomek.engine import BiomechanicsEngine

app = Flask(__name__)


def _run_simulation(params: dict) -> dict:
    """
    Run both equipment modes for all exercises using caller-supplied parameters.
    Returns JSON-serialisable dict ready for the frontend.
    """
    f_cable = float(params.get("f_cable", 50.0))
    n_points = 60

    exercises_raw = params.get("exercises", {})

    exercises = []
    for key, ex_cfg in exercises_raw.items():
        exercises.append(Exercise(
            name=ex_cfg["name"],
            joint=ex_cfg["joint"],
            angle_range_deg=tuple(ex_cfg["angle_range_deg"]),
            muscle_weights={k: float(v) for k, v in ex_cfg["muscle_weights"].items()},
            muscles_involved=list(ex_cfg["muscles_involved"]),
        ))

    # Override anatomy / device constants if provided
    device_cfg = params.get("device", {})
    pad_from_wrist = float(device_cfg.get("pad_from_wrist", 0.02))
    grip_fraction = float(device_cfg.get("grip_force_fraction", 0.05))

    eq_trad = EquipmentModel("traditional")
    eq_dev = EquipmentModel("biomek")

    # Apply overrides at runtime
    from biomek import equipment as eq_module
    eq_module.DEVICE_PAD_FROM_WRIST = pad_from_wrist
    eq_module.DEVICE_GRIP_FRACTION = grip_fraction

    engine_trad = BiomechanicsEngine(eq_trad)
    engine_dev = BiomechanicsEngine(eq_dev)

    results = []
    for ex in exercises:
        res_trad = engine_trad.sweep_rom(f_cable, ex, n_points)
        res_dev = engine_dev.sweep_rom(f_cable, ex, n_points)

        # Convert numpy arrays to plain lists for JSON serialisation
        def serialise(r):
            return {
                "angles_deg": r["angles_deg"].tolist(),
                "activations": {k: v.tolist() for k, v in r["activations"].items()},
                "stresses": {k: v.tolist() for k, v in r["stresses"].items()},
                "peak_activations": r["peak_activations"],
                "peak_stresses": r["peak_stresses"],
            }

        results.append({
            "exercise": {
                "name": ex.name,
                "joint": ex.joint,
                "muscles_involved": ex.muscles_involved,
            },
            "traditional": serialise(res_trad),
            "biomek": serialise(res_dev),
        })

    return {"f_cable": f_cable, "results": results}


@app.route("/")
def index():
    cfg = load_config()
    return render_template("index.html", config=cfg)


@app.route("/api/config")
def get_config():
    return jsonify(load_config())


@app.route("/api/simulate", methods=["POST"])
def simulate():
    params = request.get_json(force=True)
    try:
        data = _run_simulation(params)
        return jsonify({"ok": True, "data": data})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


if __name__ == "__main__":
    app.run(debug=True, port=5050, use_reloader=False)
