# BioMek — Biomechanical Simulation

A physics-based simulation comparing the **BioMek forearm pad device** against a traditional cable handle across three hypotheses:

- **H1** — Wrist joint reaction stress is reduced with BioMek
- **H2** — Tendon stress at the medial epicondyle (golfer's elbow) and lateral epicondyle (tennis elbow) is reduced
- **H3** — Target muscle activation (biceps, brachialis, deltoid) is preserved or higher at equal joint torque

---

## Scientific Basis

The simulation is grounded in peer-reviewed biomechanics literature and the OpenSim `arm26` model:

| Component | Source |
|---|---|
| Muscle parameters (Fmax, fiber length, pennation) | [Holzbaur et al. 2005](https://doi.org/10.1007/s10439-005-3320-7) — *arm26.osim* |
| Muscle force-length curve | [Thelen 2003](https://doi.org/10.1115/1.1531112) — `Thelen2003Muscle` (same as OpenSim) |
| Elbow moment arms | arm26.osim geometry · Holzbaur 2005 Fig 4 (cubic spline fit) |
| Wrist muscle elbow moment arms | Murray et al. 2000; An et al. 1981 |
| Static optimization (minimize Σa²) | [Anderson & Pandy 2001](https://doi.org/10.1115/1.1392310) |
| Epicondyle tendon CSA | Regan et al. 1991 (medial); Nimura et al. 2014 (lateral) |

All muscle parameters are taken directly from `arm26.osim` as distributed with [OpenSim](https://opensim.stanford.edu/).

---

## Simulation Results (Standard Curl, 11 lbs traditional / 14.3 lbs BioMek at equal torque)

| Metric | Traditional | BioMek | Change |
|---|---|---|---|
| Wrist joint stress | 220 kPa | 5 kPa | **−98%** |
| Medial epicondyle tendon | 326 kPa | 21 kPa | **−94%** |
| Lateral epicondyle tendon | 440 kPa | 29 kPa | **−94%** |
| Grip demand | 8.2% MVC | 0.5% MVC | **−94%** |
| Biceps Long Head activation | 28.2% MVC | 28.9% MVC | **+0.7%** |
| Brachialis activation | 20.4% MVC | 21.1% MVC | **+0.7%** |

> H3 note: BioMek requires ~30% more cable force to match the same joint torque (shorter moment arm: 23.3 cm vs 30.3 cm at wrist). At equal torque, BIC/BRA work slightly harder because wrist muscles no longer contribute free elbow flexion torque via their cross-joint moment arms (PT 14 mm, FCR 8 mm, ECRL 9 mm).

---

## Repository Structure

```
BioMek/
├── config/
│   └── simulation.yaml        # All muscle parameters, geometry, exercise definitions
├── src/
│   └── biomek/
│       ├── anatomy.py         # Muscle data, moment-arm splines, Thelen force-length
│       ├── engine.py          # Static optimization engine, wrist-elbow coupling
│       ├── equipment.py       # Traditional handle vs BioMek geometry
│       ├── exercises.py       # Exercise loader from config
│       └── visualization.py   # Matplotlib figures
│   └── main.py                # Standalone CLI simulation
├── web/
│   ├── app.py                 # Flask web app (port 5051)
│   ├── templates/index.html   # UI
│   └── static/
│       ├── css/style.css
│       └── js/app.js          # Live charts (Chart.js)
└── data/output/               # Generated figures (gitignored)
```

---

## Running Locally

### Prerequisites

```bash
pip install numpy scipy matplotlib pyyaml flask
```

### CLI simulation

```bash
cd src
python main.py
# Outputs results to terminal + saves figures to data/output/
```

### Web UI

```bash
cd web
python app.py
# Open http://localhost:5051
```

The web UI lets you adjust cable load, pad placement, and grip force fraction live, with Chart.js charts updating in real time.

---

## Key Physics

### Static Optimization

At each joint angle, the engine solves for muscle activations **a₁…aₙ ∈ [0,1]** that minimize:

```
minimize  Σ aᵢ²
subject to  Σ aᵢ · Fmax_i · cos(φᵢ) · MA_i(θ) = τ_required(θ)
```

This is the standard criterion used in OpenSim's `StaticOptimization` tool (Anderson & Pandy 2001). Solved analytically via Lagrange multipliers with iterative box-constraint clamping.

### Wrist-Elbow Coupling

When gripping a traditional handle, wrist flexors (FCR, FCU, PL, PT) and extensors (ECRB, ECRL, ECU) fire to maintain grip. Because PT, FCR, and ECRL cross the elbow, they contribute a small free flexion torque (~0.5 N·m at 11 lbs), reducing the demand on biceps/brachialis. BioMek eliminates grip, so this coupling disappears and BIC/BRA cover the full torque themselves.

### Equal-Torque Comparison

Because BioMek's pad is 2 cm proximal to the wrist vs the hand center for a traditional handle, its effective moment arm is shorter (23.3 cm vs 30.3 cm). To compare at the same joint torque, BioMek uses a proportionally higher cable force:

```
f_biomek = τ_target / (L_biomek × sin θ)
```

---

## Exercises

| Exercise | Joint | Muscles | Grip |
|---|---|---|---|
| Standard Curl | Elbow | BIClong, BICshort, BRA, TRIlong, TRIlat, TRImed | Supinated |
| Reverse Curl | Elbow | BIClong, BICshort, BRA, TRIlong, TRIlat, TRImed | Pronated |
| Lateral Raise | Shoulder | DELT_lat, DELT_ant, SUPSP | Neutral |

Additional exercises can be added in `config/simulation.yaml` without changing any Python code.

---

## References

- Holzbaur KRS, Murray WM, Delp SL. 2005. *A Model of the Upper Extremity for Simulating Musculoskeletal Surgery and Analyzing Neuromuscular Control.* Annals of Biomedical Engineering 33(6):829–840.
- Thelen DG. 2003. *Adjustment of Muscle Mechanics Model Parameters to Simulate Dynamic Contractions in Older Adults.* Journal of Biomechanical Engineering 125(1):70–77.
- Anderson FC, Pandy MG. 2001. *Static and Dynamic Optimization Solutions for Gait Are Practically Equivalent.* Journal of Biomechanical Engineering 123(4):381–390.
- Murray WM, Buchanan TS, Delp SL. 2000. *The isometric functional capacity of muscles that cross the elbow.* Journal of Biomechanics 33(8):943–952.
- An KN, Hui FC, Morrey BF, Linscheid RL, Chao EY. 1981. *Muscles across the elbow joint: a biomechanical analysis.* Journal of Biomechanics 14(10):659–669.
