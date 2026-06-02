"""All matplotlib visualization functions."""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from .exercises import Exercise

COLORS = {
    "biceps": "#e74c3c",
    "brachialis": "#e67e22",
    "brachioradialis": "#f1c40f",
    "forearm_flexors": "#95a5a6",
    "deltoid_lateral": "#3498db",
    "deltoid_anterior": "#2980b9",
    "supraspinatus": "#8e44ad",
}

JOINT_COLORS = {"wrist": "#e74c3c", "elbow": "#f39c12", "shoulder": "#3498db"}


def plot_equipment_schematic(fig: plt.Figure):
    ax = fig.add_subplot(111)
    ax.set_xlim(-2, 12)
    ax.set_ylim(-2, 8)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("BioMek Forearm Device — Top View", fontsize=16, fontweight="bold", pad=20)

    ax.add_patch(mpatches.FancyBboxPatch(
        (1, 1), 8, 5, boxstyle="round,pad=0.2",
        facecolor="none", edgecolor="#2c3e50", linewidth=3
    ))
    ax.add_patch(mpatches.FancyBboxPatch(
        (1, 0.3), 8, 1.4, boxstyle="round,pad=0.3",
        facecolor="#a8d8ea", edgecolor="#3498db", linewidth=2, alpha=0.7
    ))
    ax.text(5, 1.0, 'PADDED ARM (on forearm bone)', ha='center', va='center',
            fontsize=9, fontweight='bold', color='#2c3e50')

    ax.add_patch(mpatches.FancyBboxPatch(
        (1, 5.3), 8, 0.7, boxstyle="round,pad=0.1",
        facecolor="#fadbd8", edgecolor="#e74c3c", linewidth=2, alpha=0.7
    ))
    ax.text(5, 5.65, 'PALM REST ARM (stabilizer)', ha='center', va='center',
            fontsize=9, fontweight='bold', color='#922b21')

    for x in [1.2, 8.8]:
        ax.plot([x, x], [1.7, 5.3], color='#7f8c8d', linewidth=6, solid_capstyle='round')

    ax.annotate('', xy=(9.5, 1), xytext=(9.5, 6),
                arrowprops=dict(arrowstyle='<->', color='#2c3e50', lw=1.5))
    ax.text(10.2, 3.5, '6"', fontsize=12, ha='center', va='center', color='#2c3e50')
    ax.annotate('', xy=(1, 7), xytext=(9, 7),
                arrowprops=dict(arrowstyle='<->', color='#2c3e50', lw=1.5))
    ax.text(5, 7.4, '6" (long arms)', fontsize=10, ha='center', color='#2c3e50')
    ax.annotate('', xy=(0.3, 1.7), xytext=(0.3, 5.3),
                arrowprops=dict(arrowstyle='<->', color='#7f8c8d', lw=1.2))
    ax.text(-0.5, 3.5, '3"', fontsize=10, ha='center', va='center', color='#7f8c8d')

    ax.plot([0.2, -0.5, -0.5, 0.2], [1.0, 0.5, -0.5, -1.0],
            color='#27ae60', linewidth=3, linestyle='--')
    ax.plot([9.8, 10.5, 10.5, 9.8], [1.0, 0.5, -0.5, -1.0],
            color='#27ae60', linewidth=3, linestyle='--')
    ax.text(5, -1.2, '⟵ HARNESS LOOP (clips to cable carabiner) ⟶',
            ha='center', fontsize=10, color='#27ae60', fontweight='bold')
    ax.text(5, -1.9,
            'Blue padding = rests on forearm bone  |  Red = palm rest  |  Green = harness to cable',
            ha='center', fontsize=8, color='#7f8c8d', style='italic')


def plot_muscle_activation_comparison(fig: plt.Figure, all_results: list):
    n_ex = len(all_results)
    gs = GridSpec(1, n_ex, figure=fig, wspace=0.35)

    for idx, (exercise, res_dev, res_trad) in enumerate(all_results):
        ax = fig.add_subplot(gs[0, idx])
        muscles = [m for m in exercise.muscles_involved if m != "forearm_flexors"]
        muscles.append("forearm_flexors")

        dev_vals = [res_dev["peak_activations"].get(m, 0) for m in muscles]
        trad_vals = [res_trad["peak_activations"].get(m, 0) for m in muscles]
        x = np.arange(len(muscles))
        width = 0.35

        bars_trad = ax.bar(x - width/2, trad_vals, width, label="Traditional",
                           color=[COLORS.get(m, "#bdc3c7") for m in muscles],
                           edgecolor="black", linewidth=0.5, alpha=0.5)
        bars_dev = ax.bar(x + width/2, dev_vals, width, label="BioMek Device",
                          color=[COLORS.get(m, "#bdc3c7") for m in muscles],
                          edgecolor="black", linewidth=1.2)

        for bar in bars_trad:
            h = bar.get_height()
            if h > 1:
                ax.text(bar.get_x() + bar.get_width()/2, h + 0.5,
                        f'{h:.0f}%', ha='center', va='bottom', fontsize=7, color='#666')
        for bar in bars_dev:
            h = bar.get_height()
            if h > 1:
                ax.text(bar.get_x() + bar.get_width()/2, h + 0.5,
                        f'{h:.0f}%', ha='center', va='bottom', fontsize=7, fontweight='bold')

        ax.set_xticks(x)
        ax.set_xticklabels([m.replace("_", "\n") for m in muscles], fontsize=7)
        ax.set_ylabel("Peak Activation (% MVC)" if idx == 0 else "")
        ax.set_title(exercise.name, fontsize=12, fontweight="bold")
        ax.set_ylim(0, max(max(dev_vals), max(trad_vals)) * 1.25 + 5)

        if idx == 0:
            ax.legend(handles=[
                mpatches.Patch(facecolor='gray', alpha=0.5, edgecolor='black',
                               linewidth=0.5, label='Traditional'),
                mpatches.Patch(facecolor='gray', alpha=1.0, edgecolor='black',
                               linewidth=1.2, label='BioMek Device'),
            ], fontsize=8, loc='upper left')


def plot_joint_stress_comparison(fig: plt.Figure, all_results: list):
    ax = fig.add_subplot(111)
    joint_names_ordered = ["wrist", "elbow", "shoulder"]
    exercise_names = [ex.name for ex, _, _ in all_results]

    data_trad = {j: [] for j in joint_names_ordered}
    data_dev = {j: [] for j in joint_names_ordered}
    for _, res_dev, res_trad in all_results:
        for j in joint_names_ordered:
            data_trad[j].append(res_trad["peak_stresses"].get(j, 0) / 1000)
            data_dev[j].append(res_dev["peak_stresses"].get(j, 0) / 1000)

    x = np.arange(len(exercise_names))
    total_width = 0.7
    bar_width = total_width / (len(joint_names_ordered) * 2)

    for j_idx, jname in enumerate(joint_names_ordered):
        offset_trad = -total_width/2 + j_idx * 2 * bar_width + bar_width * 0.5
        offset_dev = offset_trad + bar_width
        color = JOINT_COLORS[jname]

        ax.bar(x + offset_trad, data_trad[jname], bar_width, color=color, alpha=0.4,
               edgecolor='black', linewidth=0.5, label=f'{jname.title()} (Trad)')
        ax.bar(x + offset_dev, data_dev[jname], bar_width, color=color, alpha=1.0,
               edgecolor='black', linewidth=1.0, label=f'{jname.title()} (BioMek)')

        for i in range(len(exercise_names)):
            vt, vd = data_trad[jname][i], data_dev[jname][i]
            if vt > 0.1:
                reduction = (1 - vd / vt) * 100
                if reduction > 5:
                    ax.text(x[i] + offset_dev, max(vt, vd) + 2,
                            f'-{reduction:.0f}%', ha='center', va='bottom',
                            fontsize=7, color=color, fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels(exercise_names, fontsize=11)
    ax.set_ylabel("Peak Joint Stress (kPa)", fontsize=11)
    ax.set_title("Joint Stress Comparison: BioMek Device vs Traditional Handle",
                 fontsize=14, fontweight="bold")
    ax.legend(fontsize=8, ncol=3, loc='upper right')
    ax.grid(axis='y', alpha=0.3)


def plot_rom_sweep(fig: plt.Figure, all_results: list):
    n_ex = len(all_results)
    gs = GridSpec(n_ex, 2, figure=fig, hspace=0.5, wspace=0.3)

    for idx, (exercise, res_dev, res_trad) in enumerate(all_results):
        angles = res_dev["angles_deg"]

        ax1 = fig.add_subplot(gs[idx, 0])
        for muscle in exercise.muscles_involved:
            color = COLORS.get(muscle, "#bdc3c7")
            label = muscle.replace("_", " ").title()
            ax1.plot(angles, res_trad["activations"][muscle], '--', color=color,
                     alpha=0.5, linewidth=1.5)
            ax1.plot(angles, res_dev["activations"][muscle], '-', color=color,
                     linewidth=2, label=label)
        ax1.set_xlabel(f'{exercise.joint.title()} Angle (°)', fontsize=9)
        ax1.set_ylabel('Activation (% MVC)', fontsize=9)
        ax1.set_title(f'{exercise.name} — Muscle Activation', fontsize=11, fontweight='bold')
        ax1.legend(fontsize=7, loc='upper left')
        ax1.grid(alpha=0.3)
        if idx == 0:
            ax1.text(0.98, 0.02, 'Solid = BioMek, Dashed = Traditional',
                     transform=ax1.transAxes, fontsize=7, ha='right', va='bottom',
                     style='italic', color='#666')

        ax2 = fig.add_subplot(gs[idx, 1])
        for jname in res_dev["stresses"]:
            color = JOINT_COLORS.get(jname, "#bdc3c7")
            ax2.plot(angles, res_trad["stresses"][jname] / 1000, '--', color=color,
                     alpha=0.5, linewidth=1.5)
            ax2.plot(angles, res_dev["stresses"][jname] / 1000, '-', color=color,
                     linewidth=2, label=jname.title())
        ax2.set_xlabel(f'{exercise.joint.title()} Angle (°)', fontsize=9)
        ax2.set_ylabel('Joint Stress (kPa)', fontsize=9)
        ax2.set_title(f'{exercise.name} — Joint Stress', fontsize=11, fontweight='bold')
        ax2.legend(fontsize=7, loc='upper left')
        ax2.grid(alpha=0.3)
        if idx == 0:
            ax2.text(0.98, 0.02, 'Solid = BioMek, Dashed = Traditional',
                     transform=ax2.transAxes, fontsize=7, ha='right', va='bottom',
                     style='italic', color='#666')


def plot_summary_dashboard(fig: plt.Figure, all_results: list, f_cable: float):
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)

    ax.text(5, 9.5, "BioMek Device — Impact Summary",
            fontsize=18, fontweight="bold", ha="center", va="top", color="#2c3e50")
    ax.text(5, 9.0, f"Cable load: {f_cable:.0f} N ({f_cable * 0.2248:.1f} lbs)",
            fontsize=11, ha="center", va="top", color="#7f8c8d")

    y = 8.2
    for exercise, res_dev, res_trad in all_results:
        ax.text(0.5, y, exercise.name, fontsize=14, fontweight="bold", color="#2c3e50")
        y -= 0.5

        ws_trad = res_trad["peak_stresses"].get("wrist", 0)
        ws_dev = res_dev["peak_stresses"].get("wrist", 0)
        es_trad = res_trad["peak_stresses"].get("elbow", 0)
        es_dev = res_dev["peak_stresses"].get("elbow", 0)
        gf_trad = res_trad["peak_activations"].get("forearm_flexors", 0)
        gf_dev = res_dev["peak_activations"].get("forearm_flexors", 0)

        ws_red = (1 - ws_dev / ws_trad) * 100 if ws_trad > 0 else 0
        es_red = (1 - es_dev / es_trad) * 100 if es_trad > 0 else 0
        gf_red = (1 - gf_dev / gf_trad) * 100 if gf_trad > 0 else 0

        ax.text(1.0, y, f"Wrist stress: -{ws_red:.0f}%", fontsize=11, color="#e74c3c")
        ax.text(4.0, y, f"Elbow stress: -{es_red:.0f}%", fontsize=11, color="#f39c12")
        ax.text(7.0, y, f"Grip demand: -{gf_red:.0f}%", fontsize=11, color="#95a5a6")
        y -= 0.5

        for m in [m for m in exercise.muscles_involved if m != "forearm_flexors"]:
            pd = res_dev["peak_activations"].get(m, 0)
            pt = res_trad["peak_activations"].get(m, 0)
            ratio = pd / pt * 100 if pt > 0 else 0
            ax.text(1.0, y,
                    f"  {m.replace('_', ' ').title()}: {pd:.1f}% MVC (= {ratio:.0f}% of traditional)",
                    fontsize=9, color="#555")
            y -= 0.35
        y -= 0.3

    ax.text(0.5, y, "Key Takeaway:", fontsize=12, fontweight="bold", color="#27ae60")
    y -= 0.45
    for line in [
        "The BioMek device virtually eliminates wrist stress and grip demand.",
        "Primary muscle activation is ~77% of traditional per unit cable load.",
        "Increase cable weight ~25-30% to match the same muscle stimulus with zero wrist strain.",
    ]:
        ax.text(0.5, y, line, fontsize=10, color="#2c3e50")
        y -= 0.35
