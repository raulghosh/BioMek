"""
BioMek Web App — Flask backend.
Serves the UI and exposes /api/simulate for live simulation results.

Run:
    cd web && python app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from flask import Flask, render_template, request, jsonify
import numpy as np

from biomek.anatomy import load_config, ELBOW_MUSCLES, SHOULDER_MUSCLES, elbow_moment_arms, shoulder_moment_arms
from biomek.equipment import EquipmentModel
from biomek.exercises import Exercise
from biomek.engine import BiomechanicsEngine

app = Flask(__name__)

LBS_TO_N = 4.4482


def _run_simulation(params: dict) -> dict:
    """Run both equipment modes for all exercises from JSON params."""
    f_cable = float(params.get("f_cable_lbs", 11)) * LBS_TO_N

    # Device overrides
    dev_cfg = params.get("device", {})
    from biomek import equipment as eq_mod
    eq_mod.DEVICE_PAD_FROM_WRIST = float(dev_cfg.get("pad_from_wrist", 0.02))
    eq_mod.DEVICE_GRIP_FRACTION  = float(dev_cfg.get("grip_force_fraction", 0.05))

    n_points = int(params.get("n_rom_points", 60))
    exercises_raw = params.get("exercises", {})

    exercises = []
    for key, ex_cfg in exercises_raw.items():
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
            grip_fmax=float(ex_cfg.get("grip_fmax", 600.0)),
            grip_pattern=ex_cfg.get("grip_pattern", "neutral"),
        ))

    eq_trad = EquipmentModel("traditional")
    eq_dev  = EquipmentModel("biomek")

    results = []
    for ex in exercises:
        res_trad = BiomechanicsEngine(eq_trad).run_simulation(ex, f_cable, n_points)
        res_dev  = BiomechanicsEngine(eq_dev).run_simulation(ex, f_cable, n_points)

        def serialise(r):
            acts = {m: r["activations"][m].tolist() for m in ex.muscles}
            acts["grip"] = r["grip_activation"].tolist()
            stresses = {
                "wrist":             r["wrist_stress"].tolist(),
                "elbow":             r["elbow_stress"].tolist(),
                "medial_epicondyle": r["medial_epicondyle_stress"].tolist(),
                "lateral_epicondyle": r["lateral_epicondyle_stress"].tolist(),
            }
            if ex.joint == "shoulder":
                stresses["shoulder"] = r["shoulder_stress"].tolist()

            peak_st = {
                "wrist":             r["peak_wrist_stress"],
                "elbow":             r["peak_elbow_stress"],
                "medial_epicondyle": r["peak_medial_epicondyle_stress"],
                "lateral_epicondyle": r["peak_lateral_epicondyle_stress"],
            }
            if ex.joint == "shoulder":
                peak_st["shoulder"] = r["peak_shoulder_stress"]

            return {
                "angles_deg":       r["angles_deg"].tolist(),
                "activations":      acts,
                "stresses":         stresses,
                "peak_activations": r["peak_activations"],
                "peak_stresses":    peak_st,
            }

        results.append({
            "exercise": {
                "name":    ex.name,
                "joint":   ex.joint,
                "muscles": ex.muscles,
            },
            "traditional": serialise(res_trad),
            "biomek":      serialise(res_dev),
        })

    return {"f_cable_lbs": params.get("f_cable_lbs", 11), "results": results}


@app.route("/")
def index():
    cfg = load_config()
    return render_template("index.html", config=cfg)


@app.route("/api/config")
def get_config():
    return jsonify(load_config())


@app.route("/api/debug")
def debug():
    import inspect
    from biomek.exercises import Exercise
    src = inspect.getfile(Exercise)
    fields = [f.name for f in Exercise.__dataclass_fields__.values()] if hasattr(Exercise, '__dataclass_fields__') else dir(Exercise)
    return jsonify({"exercise_src": src, "exercise_fields": str(fields)})


@app.route("/api/simulate", methods=["POST"])
def simulate():
    params = request.get_json(force=True)
    try:
        data = _run_simulation(params)
        return jsonify({"ok": True, "data": data})
    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        print("SIMULATE ERROR:", str(exc), flush=True)
        print(tb, flush=True)
        return jsonify({"ok": False, "error": str(exc), "trace": tb}), 400


if __name__ == "__main__":
    print(f"Starting BioMek v2 (arm26) from: {Path(__file__).resolve()}", flush=True)
    app.run(debug=True, port=5051, use_reloader=False)
