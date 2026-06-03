"""Entry point for the BioMek biomechanical simulation (standalone, no web)."""

import matplotlib.pyplot as plt
from pathlib import Path

from biomek.anatomy import load_config
from biomek.equipment import EquipmentModel
from biomek.exercises import load_exercises
from biomek.engine import BiomechanicsEngine
from biomek import visualization as viz

ROOT       = Path(__file__).parents[1]
OUTPUT_DIR = ROOT / "data" / "output"

LBS_TO_N = 4.4482


def main():
    cfg     = load_config()
    f_lbs   = cfg["simulation"]["f_cable_lbs"]
    f_cable = f_lbs * LBS_TO_N
    n_pts   = cfg["simulation"]["n_rom_points"]
    dpi     = cfg["output"]["dpi"]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("BioMek — Standalone Simulation (arm26 / Holzbaur 2005)")
    print("=" * 60)
    print(f"Cable: {f_lbs} lbs ({f_cable:.1f} N) | Thelen2003 muscle model\n")

    eq_trad = EquipmentModel("traditional")
    eq_dev  = EquipmentModel("biomek")
    exercises = load_exercises(cfg)
    all_results = []

    for ex in exercises:
        print(f"--- {ex.name} ---")
        res_trad = BiomechanicsEngine(eq_trad).run_simulation(ex, f_cable, n_pts)
        res_dev  = BiomechanicsEngine(eq_dev).run_simulation(ex, f_cable, n_pts)
        all_results.append((ex, res_dev, res_trad))

        active = [m for m in ex.muscles if ex.muscle_db[m]["role"] != "extensor"]
        for m in active + ["grip"]:
            name = m if m == "grip" else ex.muscle_db[m]["full_name"]
            pt = res_trad["peak_activations"].get(m, 0)
            pd = res_dev["peak_activations"].get(m, 0)
            print(f"  {name:28s}  Trad: {pt:5.1f}%  Device: {pd:5.1f}%")

        for j in ["wrist", "elbow", "shoulder"]:
            st = res_trad.get(f"peak_{j}_stress", 0)
            sd = res_dev.get(f"peak_{j}_stress", 0)
            if st > 0.1:
                red = (1 - sd / st) * 100
                print(f"  {j.title():12s} stress   "
                      f"Trad: {st/1000:6.1f} kPa  Device: {sd/1000:6.1f} kPa  (-{red:.0f}%)")
        print()

    # Figures
    print("Generating visualizations...")
    def _save(fig, name):
        fig.savefig(OUTPUT_DIR / name, dpi=dpi, bbox_inches="tight")
        print(f"  {name}")
        plt.close(fig)

    fig1 = plt.figure(figsize=(12, 7))
    viz.plot_equipment_schematic(fig1)
    _save(fig1, "equipment_schematic.png")

    fig2 = plt.figure(figsize=(16, 5))
    fig2.suptitle("Peak Muscle Activation — BioMek vs Traditional (arm26/Holzbaur2005)",
                  fontsize=13, fontweight="bold", y=1.02)
    viz.plot_muscle_comparison(fig2, all_results)
    _save(fig2, "muscle_activation.png")

    fig3 = plt.figure(figsize=(12, 6))
    viz.plot_joint_stress(fig3, all_results)
    _save(fig3, "joint_stress.png")

    fig4 = plt.figure(figsize=(14, 12))
    fig4.suptitle("ROM Analysis — BioMek vs Traditional (arm26/Holzbaur2005)",
                  fontsize=13, fontweight="bold")
    viz.plot_rom_sweep(fig4, all_results)
    _save(fig4, "rom_sweep.png")

    fig5 = plt.figure(figsize=(12, 8))
    viz.plot_summary(fig5, all_results, f_cable)
    _save(fig5, "summary_dashboard.png")

    print(f"\nAll figures saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
