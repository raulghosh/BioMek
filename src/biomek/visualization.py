"""Visualization functions matching the new arm26/Holzbaur result structure."""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

MC = {
    "BIClong": "#e74c3c", "BICshort": "#c0392b", "BRA": "#e67e22",
    "TRIlong": "#3498db", "TRIlat":   "#2980b9", "TRImed": "#1abc9c",
    "DELT_lat": "#3498db", "DELT_ant": "#2980b9", "SUPSP":  "#8e44ad",
    "grip": "#95a5a6",
}
JOINT_COLORS = {"wrist": "#e74c3c", "elbow": "#f39c12", "shoulder": "#3498db"}


def plot_equipment_schematic(fig):
    ax = fig.add_subplot(111)
    ax.set_xlim(-2, 12); ax.set_ylim(-2, 8)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("BioMek Forearm Device — Top View", fontsize=16, fontweight="bold", pad=20)

    ax.add_patch(mpatches.FancyBboxPatch(
        (1, 1), 8, 5, boxstyle="round,pad=0.2", facecolor="none", edgecolor="#2c3e50", linewidth=3))
    ax.add_patch(mpatches.FancyBboxPatch(
        (1, 0.3), 8, 1.4, boxstyle="round,pad=0.3",
        facecolor="#a8d8ea", edgecolor="#3498db", linewidth=2, alpha=0.7))
    ax.text(5, 1.0, 'PADDED ARM (on forearm bone)', ha='center', va='center',
            fontsize=9, fontweight='bold', color='#2c3e50')
    ax.add_patch(mpatches.FancyBboxPatch(
        (1, 5.3), 8, 0.7, boxstyle="round,pad=0.1",
        facecolor="#fadbd8", edgecolor="#e74c3c", linewidth=2, alpha=0.7))
    ax.text(5, 5.65, 'PALM REST ARM (stabilizer)', ha='center', va='center',
            fontsize=9, fontweight='bold', color='#922b21')
    for x in [1.2, 8.8]:
        ax.plot([x, x], [1.7, 5.3], color='#7f8c8d', linewidth=6, solid_capstyle='round')
    ax.annotate('', xy=(9.5,1), xytext=(9.5,6), arrowprops=dict(arrowstyle='<->', color='#2c3e50', lw=1.5))
    ax.text(10.2, 3.5, '6"', fontsize=12, ha='center', va='center')
    ax.annotate('', xy=(1,7), xytext=(9,7), arrowprops=dict(arrowstyle='<->', color='#2c3e50', lw=1.5))
    ax.text(5, 7.4, '6" (long arms)', fontsize=10, ha='center')
    ax.plot([0.2,-0.5,-0.5,0.2],[1.0,0.5,-0.5,-1.0], color='#27ae60', linewidth=3, linestyle='--')
    ax.plot([9.8,10.5,10.5,9.8],[1.0,0.5,-0.5,-1.0], color='#27ae60', linewidth=3, linestyle='--')
    ax.text(5, -1.2, 'HARNESS LOOP (clips to cable carabiner)',
            ha='center', fontsize=10, color='#27ae60', fontweight='bold')


def plot_muscle_comparison(fig, all_results):
    n_ex = len(all_results)
    gs = GridSpec(1, n_ex, figure=fig, wspace=0.35)

    for idx, (exercise, res_dev, res_trad) in enumerate(all_results):
        ax = fig.add_subplot(gs[0, idx])
        active = [m for m in exercise.muscles if exercise.muscle_db[m]["role"] != "extensor"]
        muscles = active + ["grip"]

        dv = [res_dev["peak_activations"].get(m, 0)  for m in muscles]
        tv = [res_trad["peak_activations"].get(m, 0) for m in muscles]
        colors = [MC.get(m, "#bdc3c7") for m in muscles]
        x = np.arange(len(muscles)); w = 0.35

        ax.bar(x - w/2, tv, w, color=colors, alpha=0.4, edgecolor="black", linewidth=0.5)
        ax.bar(x + w/2, dv, w, color=colors, alpha=1.0, edgecolor="black", linewidth=1.2)

        for j in range(len(muscles)):
            if tv[j] > 0.5: ax.text(x[j]-w/2, tv[j]+0.3, f'{tv[j]:.0f}%', ha='center', fontsize=6, color='#888')
            if dv[j] > 0.5: ax.text(x[j]+w/2, dv[j]+0.3, f'{dv[j]:.0f}%', ha='center', fontsize=6, fontweight='bold')

        labels = [exercise.muscle_db[m]["full_name"].replace(" ", "\n") if m != "grip" else "Grip" for m in muscles]
        ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=6)
        ax.set_ylabel("Peak Activation (%MVC)" if idx == 0 else "")
        ax.set_title(exercise.name, fontsize=11, fontweight="bold")
        ax.set_ylim(0, max(max(dv+[1]), max(tv+[1])) * 1.3 + 2)
        if idx == 0:
            ax.legend(handles=[
                mpatches.Patch(facecolor='gray', alpha=0.4, label='Traditional'),
                mpatches.Patch(facecolor='gray', alpha=1.0, label='BioMek'),
            ], fontsize=7, loc='upper left')


def plot_joint_stress(fig, all_results):
    ax = fig.add_subplot(111)
    names = [ex.name for ex, _, _ in all_results]
    x = np.arange(len(names))
    total_w = 0.7; n_j = 3; bw = total_w / (n_j * 2)

    for ji, j in enumerate(["wrist", "elbow", "shoulder"]):
        off_t = -total_w/2 + ji * 2 * bw + bw * 0.5; off_d = off_t + bw
        vt = [r_trad.get(f"peak_{j}_stress", 0) / 1000 for _, _, r_trad in all_results]
        vd = [r_dev.get(f"peak_{j}_stress", 0)  / 1000 for _, r_dev, _ in all_results]
        c = JOINT_COLORS[j]
        ax.bar(x+off_t, vt, bw, color=c, alpha=0.4, edgecolor='black', linewidth=0.5, label=f'{j.title()} (Trad)')
        ax.bar(x+off_d, vd, bw, color=c, alpha=1.0, edgecolor='black', linewidth=1.0, label=f'{j.title()} (BioMek)')
        for i in range(len(names)):
            if vt[i] > 0.5:
                red = (1 - vd[i] / vt[i]) * 100
                if red > 3: ax.text(x[i]+off_d, max(vt[i],vd[i])+2, f'-{red:.0f}%',
                                    ha='center', fontsize=7, color=c, fontweight='bold')

    ax.set_xticks(x); ax.set_xticklabels(names, fontsize=11)
    ax.set_ylabel("Peak Joint Stress (kPa)")
    ax.set_title("Joint Stress — BioMek vs Traditional (arm26/Holzbaur2005)", fontsize=13, fontweight="bold")
    ax.legend(fontsize=7, ncol=3, loc='upper right'); ax.grid(axis='y', alpha=0.3)


def plot_rom_sweep(fig, all_results):
    n_ex = len(all_results)
    gs = GridSpec(n_ex, 2, figure=fig, hspace=0.55, wspace=0.3)

    for idx, (exercise, res_dev, res_trad) in enumerate(all_results):
        angles = res_dev["angles_deg"]
        active = [m for m in exercise.muscles if exercise.muscle_db[m]["role"] != "extensor"]

        ax1 = fig.add_subplot(gs[idx, 0])
        for m in active:
            c = MC.get(m, "#bdc3c7")
            ax1.plot(angles, res_trad["activations"][m], '--', color=c, alpha=0.5, linewidth=1.5)
            ax1.plot(angles, res_dev["activations"][m],  '-',  color=c, linewidth=2, label=m)
        ax1.plot(angles, res_trad["grip_activation"], '--', color='gray', alpha=0.5)
        ax1.plot(angles, res_dev["grip_activation"],  '-',  color='gray', linewidth=2, label="Grip")
        ax1.set_xlabel(f'{exercise.joint.title()} Angle (deg)', fontsize=9)
        ax1.set_ylabel('Activation (%MVC)', fontsize=9)
        ax1.set_title(f'{exercise.name} — Activation', fontsize=10, fontweight='bold')
        ax1.legend(fontsize=6, loc='upper left'); ax1.grid(alpha=0.3)
        if idx == 0:
            ax1.text(0.98, 0.02, 'Solid=BioMek, Dashed=Traditional',
                     transform=ax1.transAxes, fontsize=6, ha='right', style='italic', color='#999')

        ax2 = fig.add_subplot(gs[idx, 1])
        ax2.plot(angles, res_trad["wrist_stress"]/1000,  '--', color='red',    alpha=0.5, linewidth=1.5)
        ax2.plot(angles, res_dev["wrist_stress"]/1000,   '-',  color='red',    linewidth=2, label="Wrist")
        ax2.plot(angles, res_trad["elbow_stress"]/1000,  '--', color='orange', alpha=0.5, linewidth=1.5)
        ax2.plot(angles, res_dev["elbow_stress"]/1000,   '-',  color='orange', linewidth=2, label="Elbow")
        if exercise.joint == "shoulder":
            ax2.plot(angles, res_trad["shoulder_stress"]/1000, '--', color='blue', alpha=0.5, linewidth=1.5)
            ax2.plot(angles, res_dev["shoulder_stress"]/1000,  '-',  color='blue', linewidth=2, label="Shoulder")
        ax2.set_xlabel(f'{exercise.joint.title()} Angle (deg)', fontsize=9)
        ax2.set_ylabel('Stress (kPa)', fontsize=9)
        ax2.set_title(f'{exercise.name} — Joint Stress', fontsize=10, fontweight='bold')
        ax2.legend(fontsize=6, loc='upper left'); ax2.grid(alpha=0.3)


def plot_summary(fig, all_results, f_cable):
    ax = fig.add_subplot(111); ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(0, 10)
    ax.text(5, 9.5, "BioMek Device — Impact Summary", fontsize=16, fontweight="bold",
            ha="center", color="#2c3e50")
    ax.text(5, 9.0, f"Cable: {f_cable:.0f}N ({f_cable*0.2248:.1f}lbs) | "
            "Muscle model: Thelen2003 | Source: arm26.osim (Holzbaur 2005)",
            fontsize=9, ha="center", color="#7f8c8d")
    y = 8.2
    for exercise, res_dev, res_trad in all_results:
        ax.text(0.5, y, exercise.name, fontsize=13, fontweight="bold", color="#2c3e50"); y -= 0.4
        ws  = res_trad["peak_wrist_stress"];  es  = res_trad["peak_elbow_stress"]
        ws_r = (1 - res_dev["peak_wrist_stress"]/ws)*100 if ws > 0 else 0
        es_r = (1 - res_dev["peak_elbow_stress"]/es)*100 if es > 0 else 0
        gr   = res_trad["peak_activations"]["grip"]
        gr_r = (1 - res_dev["peak_activations"]["grip"]/gr)*100 if gr > 0 else 0
        ax.text(1.0, y, f"Wrist: -{ws_r:.0f}%", fontsize=11, color="#e74c3c")
        ax.text(3.8, y, f"Elbow: -{es_r:.0f}%", fontsize=11, color="#f39c12")
        ax.text(6.5, y, f"Grip: -{gr_r:.0f}%",  fontsize=11, color="#95a5a6"); y -= 0.35
        for m in [m for m in exercise.muscles if exercise.muscle_db[m]["role"] != "extensor"]:
            pd = res_dev["peak_activations"].get(m, 0)
            pt = res_trad["peak_activations"].get(m, 0)
            name = exercise.muscle_db[m]["full_name"]
            ax.text(1.0, y, f"  {name}: {pd:.1f}% MVC ({pd/pt*100:.0f}% of trad)" if pt>0 else f"  {name}: {pd:.1f}%",
                    fontsize=8, color="#555"); y -= 0.28
        y -= 0.2
    ax.text(0.5, y, "Key Takeaway:", fontsize=11, fontweight="bold", color="#27ae60"); y -= 0.35
    ax.text(0.5, y, "Device eliminates ~98% of wrist stress and ~95% of grip demand.", fontsize=10, color="#2c3e50"); y -= 0.3
    ax.text(0.5, y, "Increase cable weight ~25-30% to match traditional muscle stimulus.", fontsize=10, color="#2c3e50")
