# BioMek Forearm Device — Biomechanical Simulation Plan

## 1. Equipment Description

A rectangular PVC frame (6″ × 3″) that redirects cable-machine force from the hand/grip to the forearm bone.

```
         3" (short arm)
    ┌──────────────────────┐
    │                      │
6"  │  PALM REST ARM       │ 6"   PADDED FOREARM ARM
    │  (no padding)        │      (pool-noodle padding)
    │                      │
    └──────────────────────┘
         3" (short arm)
              │
         HARNESS LOOP ──► connects to cable carabiner
```

- **Padded arm** (6″): rests on ulna/radius just above wrist joint
- **Palm arm** (6″): rests in palm — stabilizer only, minimal grip
- **Harness**: soft loop through one long arm, clips to cable carabiner

### Exercise Positions

| Exercise         | Padded arm placement       | Cable direction | Primary muscles          |
|-----------------|---------------------------|-----------------|--------------------------|
| Standard curl   | Underside of forearm (volar) | Low pulley, up  | Biceps, brachialis       |
| Reverse curl    | Top of forearm (dorsal)    | Low pulley, up  | Brachioradialis, biceps  |
| Lateral raise   | Underside of forearm       | Low pulley, lateral | Lateral deltoid, supraspinatus |

---

## 2. Anatomy Model Constants

All lengths in meters, forces in Newtons.

```python
ANATOMY = {
    # Segment lengths
    "upper_arm_length": 0.30,        # shoulder to elbow
    "forearm_length": 0.25,          # elbow to wrist
    "hand_length": 0.10,             # wrist to mid-palm (grip center)
    
    # Muscle insertion distances from joint center
    "biceps_insertion": 0.04,        # from elbow joint (on radius tuberosity)
    "brachialis_insertion": 0.03,    # from elbow (on ulna coronoid)
    "brachioradialis_insertion": 0.20,# from elbow (on distal radius)
    "deltoid_insertion": 0.15,       # from shoulder (on deltoid tuberosity)
    "supraspinatus_insertion": 0.02, # from shoulder (on greater tubercle)
    
    # Muscle max force (proportional to PCSA, in Newtons)
    "biceps_Fmax": 800,
    "brachialis_Fmax": 1000,
    "brachioradialis_Fmax": 200,
    "forearm_flexors_Fmax": 600,     # grip muscles
    "deltoid_lateral_Fmax": 1200,
    "deltoid_anterior_Fmax": 1200,
    "supraspinatus_Fmax": 400,
    
    # Joint reference cross-section (for stress normalization)
    "wrist_ref_area": 0.0006,        # m² (~6 cm²)
    "elbow_ref_area": 0.0012,        # m² (~12 cm²)
    "shoulder_ref_area": 0.0020,     # m² (~20 cm²)
}
```

### Muscle Moment Arm Functions

Moment arms vary with joint angle. Use simplified linear/sinusoidal models:

- **Biceps moment arm at elbow**: `d_bicep(θ) = 0.04 × (1 + 0.5 × sin(θ))` — peaks ~90°
- **Brachialis**: `d_brach(θ) = 0.03 × (1 + 0.3 × sin(θ))`
- **Brachioradialis**: `d_br(θ) = 0.05 × (1 + 0.2 × sin(θ))`
- **Deltoid (shoulder abduction)**: `d_delt(θ) = 0.02 × (1 + 2.0 × sin(θ))` — peaks ~90°

Where θ = joint angle (0 = fully extended).

---

## 3. Force Application Model

### Traditional Cable Handle
- Force applied at: **hand center** (grip)
- Distance from elbow: `L_forearm + L_hand/2 = 0.25 + 0.05 = 0.30 m`
- Grip force required: `F_grip = F_cable` (100% of cable load)
- Wrist torque: `τ_wrist = F_cable × L_hand/2 = F_cable × 0.05`

### BioMek Device
- Force applied at: **forearm pad** (2 cm above wrist = 23 cm from elbow)
- Distance from elbow: `L_forearm - 0.02 = 0.23 m`
- Grip force required: `F_grip ≈ 0.05 × F_cable` (stabilization only, 5%)
- Wrist torque: `τ_wrist ≈ 0` (force bypasses wrist joint)

### Force Application Ratio
```
R_moment = L_device / L_traditional = 0.23 / 0.30 = 0.767
```
The device creates ~23% less external torque about the elbow per unit cable load, meaning the same cable weight is slightly easier to curl. Wrist torque drops by ~100%.

---

## 4. Biomechanics Engine — Per-Exercise Calculations

### 4.1 Elbow Flexion Exercises (Curls)

For each elbow angle θ in [10°, 150°] with step 5°:

**Step A: External torque about elbow**
```
# Cable angle relative to forearm — approximated
# Low pulley: cable roughly vertical when arm is at side
α = angle_between(cable_direction, forearm_direction)

# Traditional
τ_ext_trad = F_cable × L_trad × sin(α)

# Device  
τ_ext_dev = F_cable × L_device × sin(α)
```

For a low pulley curl, simplify: cable direction ≈ vertical, forearm angle from vertical = (180° - θ_elbow). So `sin(α) ≈ sin(θ_elbow)` when arm is at side.

```
τ_ext = F_cable × L × sin(θ)
```

**Step B: Muscle force distribution**

Total muscle torque must equal external torque (static equilibrium):
```
τ_ext = F_bicep × d_bicep(θ) + F_brach × d_brach(θ) + F_br × d_br(θ)
```

Distribute using PCSA-weighted sharing:
```
w_i = PCSA_i / Σ(PCSA_j)   for each elbow flexor
F_i = (τ_ext / d_i(θ)) × w_i
activation_i = F_i / F_max_i × 100   (% MVC)
```

For **standard curl** (supinated grip): biceps = 45%, brachialis = 40%, brachioradialis = 15%
For **reverse curl** (pronated grip): biceps = 25%, brachialis = 35%, brachioradialis = 40%

**Step C: Grip/forearm flexor activation**
```
Traditional: activation_grip = (F_cable / forearm_flexors_Fmax) × 100
Device: activation_grip = (0.05 × F_cable / forearm_flexors_Fmax) × 100
```

**Step D: Joint stress**
```
# Wrist stress
τ_wrist_trad = F_cable × (L_hand / 2)
τ_wrist_dev = 0
stress_wrist = τ_wrist / wrist_ref_area

# Elbow stress (joint reaction force)
# Sum of all muscle forces + cable force component
F_elbow_reaction = sqrt((ΣF_muscle_x + F_cable_x)² + (ΣF_muscle_y + F_cable_y)²)
stress_elbow = F_elbow_reaction / elbow_ref_area
```

### 4.2 Shoulder Abduction (Lateral Raise)

For each shoulder abduction angle φ in [5°, 90°] with step 5°:

**Cable direction**: from low side pulley, roughly horizontal/upward.

```
# Arm weight torque (forearm+hand ≈ 1.5 kg)
τ_gravity = m_arm × g × L_arm_cg × cos(φ)

# Cable torque about shoulder
# Traditional: force at hand, distance = full arm length
L_trad_shoulder = L_upper_arm + L_forearm + L_hand/2 = 0.65 m
L_dev_shoulder = L_upper_arm + L_forearm - 0.02 = 0.53 m

τ_cable = F_cable × L × sin(angle_between_cable_and_arm)
```

**Muscle activation** for lateral raise:
- Lateral deltoid: 60% of torque
- Anterior deltoid: 25%
- Supraspinatus: 15%

Same grip and wrist stress calculations as curls.

---

## 5. Visualization Plan

Generate **4 output figures**:

### Figure 1: Equipment Schematic (`equipment_schematic.png`)
- Top-down view of the rectangular frame
- Labels for each component
- Annotations for dimensions

### Figure 2: Muscle Activation Comparison (`muscle_activation.png`)
- 3×2 grid: rows = exercises (standard curl, reverse curl, lateral raise), cols = (device, traditional)
- Bar charts showing peak muscle activation (% MVC) for each muscle
- Color-coded bars: biceps=red, brachialis=orange, brachioradialis=yellow, deltoid=blue, grip=gray

### Figure 3: Joint Stress Comparison (`joint_stress.png`)
- Grouped bar chart: 3 exercises × 2 conditions (device vs traditional)
- Bars for wrist stress and elbow stress (+ shoulder for lateral raise)
- Show percentage reduction annotations

### Figure 4: ROM Sweep (`rom_sweep.png`)
- 3 rows (one per exercise)
- Line plots showing muscle activation vs joint angle
- Solid lines = device, dashed = traditional
- Second y-axis or subplot for joint stress vs angle

---

## 6. Code Structure (Single File: `biomek_sim.py`)

```
biomek_sim.py
├── SECTION 1: Imports & Config
│   └── All constants from Section 2 above
├── SECTION 2: AnatomyModel class
│   ├── __init__(): set segment lengths, muscle params
│   ├── muscle_moment_arm(muscle, joint, angle): returns moment arm
│   └── muscle_max_force(muscle): returns Fmax
├── SECTION 3: EquipmentModel class
│   ├── __init__(mode): "traditional" or "biomek"
│   ├── force_application_distance(joint): distance from joint to force point
│   ├── grip_force_fraction(): 1.0 for traditional, 0.05 for biomek
│   └── wrist_torque(F_cable): torque at wrist
├── SECTION 4: Exercise class
│   ├── __init__(name, joint, angle_range, muscle_weights, cable_direction)
│   └── Stores exercise-specific parameters
├── SECTION 5: BiomechanicsEngine class
│   ├── __init__(anatomy, equipment)
│   ├── external_torque(F_cable, angle, exercise): joint torque from cable
│   ├── muscle_activations(F_cable, angle, exercise): dict of {muscle: %MVC}
│   ├── joint_stress(F_cable, angle, exercise): dict of {joint: stress_value}
│   └── sweep_rom(F_cable, exercise): run across full ROM, return DataFrame-like dict
├── SECTION 6: Visualization functions
│   ├── plot_equipment_schematic(ax)
│   ├── plot_muscle_comparison(ax, results_device, results_trad, exercise_name)
│   ├── plot_joint_stress_comparison(ax, all_results)
│   └── plot_rom_sweep(ax, sweep_device, sweep_trad, exercise_name)
└── SECTION 7: main()
    ├── Create anatomy, exercises
    ├── Run engine for each exercise × each equipment mode
    ├── Generate all 4 figures
    └── Save to output directory
```

---

## 7. Key Parameters for Simulation Run

```python
F_CABLE = 50  # Newtons (~11 lbs) — moderate cable weight
EXERCISES = [
    Exercise("Standard Curl", joint="elbow", angles=(10, 150),
             muscle_weights={"biceps": 0.45, "brachialis": 0.40, "brachioradialis": 0.15}),
    Exercise("Reverse Curl", joint="elbow", angles=(10, 150),
             muscle_weights={"biceps": 0.25, "brachialis": 0.35, "brachioradialis": 0.40}),
    Exercise("Lateral Raise", joint="shoulder", angles=(5, 90),
             muscle_weights={"deltoid_lateral": 0.60, "deltoid_anterior": 0.25, "supraspinatus": 0.15}),
]
```

---

## 8. Expected Results Summary

| Metric                    | Standard Curl (Device vs Trad) | Reverse Curl | Lateral Raise |
|--------------------------|-------------------------------|--------------|---------------|
| Wrist stress reduction   | ~95-100%                      | ~95-100%     | ~95-100%      |
| Elbow stress reduction   | ~10-20%                       | ~10-20%      | N/A           |
| Grip muscle activation   | ~95% reduction                | ~95% reduction| ~95% reduction|
| Primary muscle activation| ~77% of traditional           | ~77%         | ~82%          |

The device trades a small reduction in peak muscle torque demand for massive wrist/grip relief. Users can compensate by increasing cable weight ~25% to match the same muscle stimulus.

---

## 9. How to Extend

- Add more exercises (face pulls, tricep pushdowns, etc.)
- Add 3D model using matplotlib 3D or VPython
- Add animation of the ROM sweep
- Include fatigue modeling over sets/reps
- Add EMG validation data overlay
