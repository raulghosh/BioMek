"""Entry point for the BioMek biomechanical simulation."""

import os
import matplotlib.pyplot as plt
from pathlib import Path

from biomek.anatomy import load_config
from biomek.equipment import EquipmentModel
from biomek.exercises import load_exercises
from biomek.engine import BiomechanicsEngine
from biomek import visualization as viz

ROOT = Path(__file__).parents[1]
OUTPUT_DIR = ROOT / "data" / "output"


def main():
    cfg = load_config()
    f_cable: float = cfg["simulation"]["f_cable"]
    n_points: int = cfg["simulation"]["n_rom_points"]
    dpi: int = cfg["output"]["dpi"]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("BioMek Forearm Device — Biomechanical Simulation")
    print("=" * 60)
    print(f"Cable load: {f_cable:.0f} N ({f_cable * 0.2248:.1f} lbs)\n")

    eq_trad = EquipmentModel("traditional")
    eq_dev = EquipmentModel("biomek")
    engine_trad = BiomechanicsEngine(eq_trad)
    engine_dev = BiomechanicsEngine(eq_dev)

    exercises = load_exercises(cfg)
    all_results = []

    for ex in exercises:
        print(f"--- {ex.name} ---")
        res_trad = engine_trad.sweep_rom(f_cable, ex, n_points)
        res_dev = engine_dev.sweep_rom(f_cable, ex, n_points)
        all_results.append((ex, res_dev, res_trad))

        print("  Peak muscle activations (% MVC):")
        for m in ex.muscles_involved:
            pt = res_trad["peak_activations"].get(m, 0)
            pd = res_dev["peak_activations"].get(m, 0)
            print(f"    {m.replace('_', ' ').title():22s}  Trad: {pt:6.1f}%  Device: {pd:6.1f}%")

        print("  Peak joint stresses (kPa):")
        for j, st_val in res_trad["peak_stresses"].items():
            sd_val = res_dev["peak_stresses"][j]
            reduction = (1 - sd_val / st_val) * 100 if st_val > 0 else 0
            print(f"    {j.title():12s}  Trad: {st_val/1000:8.1f}  Device: {sd_val/1000:8.1f}  (-{reduction:.0f}%)")
        print()

    print("Generating visualizations...")
    _save = lambda fig, name: (
        fig.savefig(OUTPUT_DIR / name, dpi=dpi, bbox_inches="tight"),
        print(f"  Saved {name}"),
        plt.close(fig),
    )

    fig1 = plt.figure(figsize=(12, 7))
    viz.plot_equipment_schematic(fig1)
    _save(fig1, "equipment_schematic.png")

    fig2 = plt.figure(figsize=(16, 6))
    fig2.suptitle("Peak Muscle Activation: BioMek Device vs Traditional Handle",
                  fontsize=14, fontweight="bold", y=1.02)
    viz.plot_muscle_activation_comparison(fig2, all_results)
    _save(fig2, "muscle_activation.png")

    fig3 = plt.figure(figsize=(12, 6))
    viz.plot_joint_stress_comparison(fig3, all_results)
    _save(fig3, "joint_stress.png")

    fig4 = plt.figure(figsize=(14, 12))
    fig4.suptitle("Range of Motion Analysis: BioMek vs Traditional",
                  fontsize=14, fontweight="bold")
    viz.plot_rom_sweep(fig4, all_results)
    _save(fig4, "rom_sweep.png")

    fig5 = plt.figure(figsize=(12, 8))
    viz.plot_summary_dashboard(fig5, all_results, f_cable)
    _save(fig5, "summary_dashboard.png")

    print("\nSimulation complete. All figures saved to data/output/")


if __name__ == "__main__":
    main()
