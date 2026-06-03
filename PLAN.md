# BioMek Forearm Device — Simulation Plan (OpenSim-Based)

## Overview

This simulation compares the BioMek forearm cable attachment against a traditional cable handle using musculoskeletal models from OpenSim (opensim.stanford.edu). All muscle parameters come from the **arm26.osim** model (Holzbaur et al. 2005, Thelen 2003).

## Architecture: Two-Tier Approach

| File | Requires OpenSim? | What it uses |
|------|-------------------|--------------|
| `biomek_opensim.py` | Yes (conda install) | OpenSim API: loads arm26.osim, calls `muscle.computeMomentArm()` for anatomically exact moment arms, then runs static optimization |
| `biomek_sim.py` | No (numpy + scipy + matplotlib) | Same arm26 muscle parameters (Fmax, fiber length, pennation from Thelen2003) + published moment arm curves from Holzbaur 2005 |

Both produce the same output format. The standalone version is a validated approximation; the OpenSim version is ground truth.

---

## 1. Source Model: arm26.osim

From: https://github.com/opensim-org/opensim-models/tree/master/Models/Arm26

**Bodies**: base (thorax), r_humerus, r_ulna_radius_hand
**Joints**: r_shoulder (CustomJoint, `r_shoulder_elev`), r_elbow (CustomJoint, `r_elbow_flex`)
**Muscle model**: Thelen2003Muscle

### Muscle Parameters (extracted directly from arm26.osim)

| Muscle | Fmax (N) | Opt. fiber (m) | Tendon slack (m) | Pennation (rad) | Role |
|--------|---------|----------------|-------------------|------------------|------|
| BIClong | 624.3 | 0.1157 | 0.2723 | 0.0 | Flexor |
| BICshort | 435.56 | 0.1321 | 0.1923 | 0.0 | Flexor |
| BRA | 987.26 | 0.0858 | 0.0535 | 0.0 | Flexor |
| TRIlong | 798.52 | 0.134 | 0.143 | 0.2094 | Extensor |
| TRIlat | 624.3 | 0.1138 | 0.098 | 0.1571 | Extensor |
| TRImed | 624.3 | 0.1138 | 0.0908 | 0.1571 | Extensor |

Reference: Holzbaur KRS, Murray WM, Delp SL (2005). Ann Biomed Eng, 33: 829-840.

### Shoulder Muscles (from full upper extremity model)

For lateral raise, arm26 lacks deltoids. Use Holzbaur 2005 full model values:

| Muscle | Fmax (N) | Opt. fiber (m) | Pennation | Role |
|--------|---------|----------------|-----------|------|
| DELT_lat | 1142.6 | 0.0838 | 15° | Abductor |
| DELT_ant | 1218.9 | 0.0976 | 22° | Abductor |
| SUPSP | 487.8 | 0.0682 | 7° | Abductor |

---

## 2. Equipment Model

```
         3" (short arm)
    ┌──────────────────────┐
    │                      │
6"  │  PALM REST ARM       │ 6"   PADDED FOREARM ARM
    │                      │      (pool-noodle padding)
    └──────────────────────┘
         3" (short arm)
              │
         HARNESS LOOP → cable carabiner
```

### Force Application Points

| Condition | Application point | Distance from elbow | Grip fraction |
|-----------|------------------|--------------------:|:-------------:|
| Traditional handle | Palm center | 0.303 m | 100% |
| BioMek device | Forearm pad (2cm above wrist) | 0.233 m | 5% |

**Moment ratio**: 0.233 / 0.303 = **0.769** → device creates ~23% less external torque per unit cable load.

---

## 3. Physics: Static Optimization

At each joint angle θ:

### Step 1: External torque
```
τ_ext = F_cable × L_force_point × sin(θ)
```
where `L_force_point` differs between traditional and device.

### Step 2: Muscle activations (minimize metabolic cost)
```
minimize  Σ(a_i²)
subject to  Σ(a_i × Fmax_i × cos(penn_i) × ma_i(θ)) = τ_ext
            0 ≤ a_i ≤ 1
```
Solved with scipy SLSQP. `ma_i(θ)` = moment arm from OpenSim or Holzbaur curves.

### Step 3: Joint stress
```
Wrist:   stress = sqrt(F_grip² + (τ_wrist / 0.02)²) / A_wrist
Elbow:   stress = sqrt(ΣF_muscle² + (F_cable × cos(θ))²) / A_elbow
```
Traditional: `F_grip = F_cable`, `τ_wrist = F_cable × 0.05`
BioMek: `F_grip = 0.05 × F_cable`, `τ_wrist = 0`

---

## 4. OpenSim API Workflow (biomek_opensim.py)

```python
import opensim as osim

model = osim.Model("arm26.osim")
state = model.initSystem()

# Lock shoulder, sweep elbow
shoulder = model.getCoordinateSet().get("r_shoulder_elev")
elbow = model.getCoordinateSet().get("r_elbow_flex")
shoulder.setLocked(state, True)

for angle in angles_rad:
    elbow.setValue(state, angle)
    model.realizeVelocity(state)
    model.equilibrateMuscles(state)

    for muscle in model.getMuscles():
        ma = muscle.computeMomentArm(state, elbow)  # ← key API call
        Fmax = muscle.getMaxIsometricForce()
```

### Installation
```bash
conda create -n biomek python=3.10 numpy matplotlib scipy
conda activate biomek
conda install -c opensim-org opensim
git clone https://github.com/opensim-org/opensim-models.git
python biomek_opensim.py --model opensim-models/Models/Arm26/arm26.osim
```

---

## 5. Standalone Fallback (biomek_sim.py)

Uses the same Fmax values from arm26.osim but approximates moment arms with polynomial fits to Holzbaur 2005 Fig. 4:

```python
# Biceps long head moment arm (meters)
ma_BIClong = 0.048 × sin(0.88θ + 0.25) × clip(1 - 0.12(θ-1.4)², 0.55, 1)
```

Implements Thelen2003 force-length:
```python
f_AL(l̃) = exp(-(l̃ - 1)² / γ)     # γ = 0.5
f_PL(l̃) = (exp(4(l̃-1)/0.6) - 1) / (exp(4) - 1)
F = Fmax × [a × f_AL + f_PL] × cos(pennation)
```

---

## 6. Exercises

| Exercise | Joint | ROM | Active muscles | Model |
|----------|-------|-----|---------------|-------|
| Standard Curl | Elbow | 10°-140° | BIClong, BICshort, BRA + grip | arm26 |
| Reverse Curl | Elbow | 10°-140° | BIClong, BICshort, BRA + grip | arm26 |
| Lateral Raise | Shoulder | 5°-90° | DELT_lat, DELT_ant, SUPSP + grip | Holzbaur full UE |

For reverse curl: same muscles, same moment arms (elbow flexion mechanics are identical in this model; the difference is grip-related stress which the device eliminates). In a pronated grip with a traditional handle, wrist extensors are additionally loaded — the device eliminates this entirely.

---

## 7. Output Files

| File | Content |
|------|---------|
| `equipment_schematic.png` | Device top-view diagram |
| `muscle_activation.png` | Bar charts: peak activation per exercise |
| `joint_stress.png` | Grouped bars: wrist/elbow/shoulder stress |
| `rom_sweep.png` | Line plots: activation & stress vs joint angle |
| `summary_dashboard.png` | Text summary with percentage reductions |
| `opensim_results.csv` | Raw data (OpenSim version only) |

---

## 8. How to Extend

1. **Full upper extremity**: Replace arm26 with `MOBL_ARMS_fixed_41.osim` — adds wrist DOF, deltoids, rotator cuff. Apply external force via `osim.PrescribedForce` on the hand/forearm body.
2. **Forward dynamics**: Use `osim.Manager` to simulate the full curl motion with muscle controllers.
3. **Static Optimization tool**: Use `osim.StaticOptimization` with prescribed kinematics (`.mot` file) for the gold-standard approach.
4. **Joint reaction analysis**: Add `osim.JointReaction` to the analysis set to get exact joint contact forces.
5. **EMG validation**: Overlay experimental EMG data on the activation curves.
6. **Fatigue model**: Add a `DeGroote2016` or custom fatigue model to simulate multi-set performance.

---

## 9. Key References

- arm26 model: https://github.com/opensim-org/opensim-models/tree/master/Models/Arm26
- OpenSim Python API: https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53085346/Scripting+in+Python
- build_simple_arm_model.py: https://github.com/opensim-org/opensim-core/blob/main/Bindings/Python/examples/build_simple_arm_model.py
- Holzbaur 2005: https://doi.org/10.1007/s10439-005-3320-7
- Thelen 2003: https://doi.org/10.1115/1.1531112
- OpenSim conda: https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53116061/Conda+Package
