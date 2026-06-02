/* ============================================================
   BioMek Simulation — Frontend App
   ============================================================ */

// ── Defaults (mirroring simulation.yaml) ─────────────────────
const LBS_TO_N = 4.4482;
const KG_TO_N  = 9.8066;

function fmtWeight(lbs) {
  return `${lbs} lbs (${(lbs / 2.2046).toFixed(1)} kg)`;
}

const DEFAULTS = {
  f_cable: 11,   // stored in lbs internally; converted to N on API call
  pad_from_wrist: 2,       // cm
  grip_force_fraction: 5,  // %
  exercises: {
    standard_curl: {
      name: "Standard Curl", joint: "elbow",
      angle_range_deg: [10, 150],
      muscles_involved: ["biceps","brachialis","brachioradialis","forearm_flexors"],
      muscle_weights: { biceps: 45, brachialis: 40, brachioradialis: 15 }
    },
    reverse_curl: {
      name: "Reverse Curl", joint: "elbow",
      angle_range_deg: [10, 150],
      muscles_involved: ["biceps","brachialis","brachioradialis","forearm_flexors"],
      muscle_weights: { biceps: 25, brachialis: 35, brachioradialis: 40 }
    },
    lateral_raise: {
      name: "Lateral Raise", joint: "shoulder",
      angle_range_deg: [5, 90],
      muscles_involved: ["deltoid_lateral","deltoid_anterior","supraspinatus","forearm_flexors"],
      muscle_weights: { deltoid_lateral: 60, deltoid_anterior: 25, supraspinatus: 15 }
    }
  }
};

const MUSCLE_COLORS = {
  biceps:           "#e74c3c",
  brachialis:       "#e67e22",
  brachioradialis:  "#f1c40f",
  forearm_flexors:  "#95a5a6",
  deltoid_lateral:  "#3498db",
  deltoid_anterior: "#2980b9",
  supraspinatus:    "#8e44ad",
};

const JOINT_COLORS = { wrist: "#f85149", elbow: "#d29922", shoulder: "#388bfd" };

const GREEN = "#3fb950";
const TRAD_COLOR = "rgba(120,120,140,0.7)";

// ── State ─────────────────────────────────────────────────────
let state = JSON.parse(JSON.stringify(DEFAULTS));
let activeExKey = "standard_curl";
let charts = {};       // { exKey: { rom_act, rom_stress, bar_act, bar_stress } }
let debounceTimer = null;
let lastResults = null;

// ── Utility ───────────────────────────────────────────────────
const $ = id => document.getElementById(id);

function pct(dev, trad) {
  if (!trad) return 0;
  return Math.round((1 - dev / trad) * 100);
}

function fmtPct(v) {
  if (v === null || isNaN(v)) return "—";
  return (v > 0 ? "-" : "+") + Math.abs(v) + "%";
}

function muscleLabel(k) {
  return k.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

function clampWeights(weights) {
  // Normalise non-grip muscles to sum to 100
  const keys = Object.keys(weights);
  const total = keys.reduce((s, k) => s + weights[k], 0);
  if (total === 0) return;
  keys.forEach(k => weights[k] = Math.round(weights[k] / total * 100));
}

// ── Build sidebar exercise tabs ───────────────────────────────
function buildSidebarTabs() {
  const container = $("ex-tabs");
  container.innerHTML = "";
  Object.keys(state.exercises).forEach(key => {
    const btn = document.createElement("button");
    btn.className = "ex-tab" + (key === activeExKey ? " active" : "");
    btn.textContent = state.exercises[key].name;
    btn.onclick = () => { activeExKey = key; refreshSidebarTabs(); renderMuscleWeights(); };
    container.appendChild(btn);
  });
}

function refreshSidebarTabs() {
  document.querySelectorAll(".ex-tab").forEach((btn, i) => {
    const key = Object.keys(state.exercises)[i];
    btn.classList.toggle("active", key === activeExKey);
  });
}

// ── Build muscle weight sliders ───────────────────────────────
function renderMuscleWeights() {
  const section = $("muscle-weight-section");
  section.innerHTML = "";
  const ex = state.exercises[activeExKey];
  const primaries = ex.muscles_involved.filter(m => m !== "forearm_flexors");

  primaries.forEach(muscle => {
    const val = ex.muscle_weights[muscle] || 0;

    const row = document.createElement("div");
    row.className = "weight-row";

    const lbl = document.createElement("div");
    lbl.className = "weight-label";
    lbl.innerHTML = `<span>${muscleLabel(muscle)}</span><span id="wlbl-${muscle}">${val}%</span>`;

    const sl = document.createElement("input");
    sl.type = "range"; sl.min = 1; sl.max = 98; sl.step = 1; sl.value = val;
    sl.style.accentColor = MUSCLE_COLORS[muscle] || GREEN;

    // Style the track to match muscle colour
    sl.addEventListener("input", () => {
      ex.muscle_weights[muscle] = parseInt(sl.value);
      // Proportionally redistribute remaining weight
      const others = primaries.filter(m => m !== muscle);
      const remaining = 100 - parseInt(sl.value);
      const otherTotal = others.reduce((s, m) => s + (ex.muscle_weights[m] || 1), 0);
      others.forEach(m => {
        ex.muscle_weights[m] = Math.max(1, Math.round((ex.muscle_weights[m] / otherTotal) * remaining));
      });
      renderMuscleWeights();    // re-render sliders with updated values
      buildSidebarTabs();
      scheduleSimulate();
    });

    const barBg = document.createElement("div");
    barBg.className = "weight-bar-bg";
    const bar = document.createElement("div");
    bar.className = "weight-bar";
    bar.style.width = val + "%";
    bar.style.background = MUSCLE_COLORS[muscle] || GREEN;
    barBg.appendChild(bar);

    row.appendChild(lbl);
    row.appendChild(sl);
    row.appendChild(barBg);
    section.appendChild(row);
  });

  // Weight sum warning
  const total = primaries.reduce((s, m) => s + (ex.muscle_weights[m] || 0), 0);
  $("weight-warn").style.display = Math.abs(total - 100) > 2 ? "block" : "none";
}

// ── Build main exercise strip + panels ───────────────────────
function buildMainPanels() {
  const strip = $("main-ex-strip");
  const panels = $("exercise-panels");
  strip.innerHTML = "";
  panels.innerHTML = "";

  Object.keys(state.exercises).forEach(key => {
    const ex = state.exercises[key];

    // Tab
    const tab = document.createElement("button");
    tab.className = "ex-strip-tab" + (key === activeExKey ? " active" : "");
    tab.textContent = ex.name;
    tab.dataset.key = key;
    tab.onclick = () => switchMainTab(key);
    strip.appendChild(tab);

    // Panel
    const panel = document.createElement("div");
    panel.id = "expanel-" + key;
    panel.style.display = key === activeExKey ? "flex" : "none";
    panel.style.flexDirection = "column";
    panel.style.gap = "16px";
    panel.innerHTML = `
      <div class="charts-2col">
        <div class="chart-card">
          <div class="chart-title"><div class="dot green"></div> Muscle Activation vs Joint Angle</div>
          <div class="chart-wrap" style="height:240px;position:relative;">
            <canvas id="chart-romact-${key}"></canvas>
            <div class="loading-overlay" id="lo-romact-${key}"><div class="spinner"></div></div>
          </div>
        </div>
        <div class="chart-card">
          <div class="chart-title"><div class="dot gold"></div> Joint Stress vs Joint Angle</div>
          <div class="chart-wrap" style="height:240px;position:relative;">
            <canvas id="chart-romst-${key}"></canvas>
            <div class="loading-overlay" id="lo-romst-${key}"><div class="spinner"></div></div>
          </div>
        </div>
      </div>
      <div class="charts-2col">
        <div class="chart-card">
          <div class="chart-title"><div class="dot green"></div> Peak Muscle Activation (% MVC)</div>
          <div class="chart-wrap" style="height:220px;position:relative;">
            <canvas id="chart-baract-${key}"></canvas>
            <div class="loading-overlay" id="lo-baract-${key}"><div class="spinner"></div></div>
          </div>
        </div>
        <div class="chart-card">
          <div class="chart-title"><div class="dot red"></div> Peak Joint Stress (kPa)</div>
          <div class="chart-wrap" style="height:220px;position:relative;">
            <canvas id="chart-barst-${key}"></canvas>
            <div class="loading-overlay" id="lo-barst-${key}"><div class="spinner"></div></div>
          </div>
        </div>
      </div>
      <div class="chart-card" style="padding:0;overflow:hidden;">
        <div style="padding:14px 18px 0;font-size:12px;font-weight:600;color:var(--text-muted);
                    text-transform:uppercase;letter-spacing:0.5px;">Full Comparison Table</div>
        <table class="summary-table" id="table-${key}" style="margin-top:8px;"></table>
      </div>
    `;
    panels.appendChild(panel);
  });
}

function switchMainTab(key) {
  activeExKey = key;
  document.querySelectorAll(".ex-strip-tab").forEach(t => {
    t.classList.toggle("active", t.dataset.key === key);
  });
  Object.keys(state.exercises).forEach(k => {
    const p = $("expanel-" + k);
    if (p) p.style.display = k === key ? "flex" : "none";
  });
  refreshSidebarTabs();
  renderMuscleWeights();
  // Reset angle to range start for the new exercise and restart
  _animAngle = state.exercises[key]?.angle_range_deg?.[0] ?? 10;
  _animDir   = 1;
  startAnimation();
}

// ── Chart helpers ─────────────────────────────────────────────
const CHART_DEFAULTS = {
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration: 300 },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: "#161b22",
      borderColor: "#30363d",
      borderWidth: 1,
      titleColor: "#e6edf3",
      bodyColor: "#8b949e",
    }
  },
  scales: {
    x: {
      grid: { color: "rgba(48,54,61,0.5)" },
      ticks: { color: "#8b949e", font: { size: 10 } },
    },
    y: {
      grid: { color: "rgba(48,54,61,0.5)" },
      ticks: { color: "#8b949e", font: { size: 10 } },
    }
  }
};

function mkLineChart(canvasId, datasets, xLabel, yLabel) {
  const ctx = $(canvasId);
  if (!ctx) return null;
  const cfg = JSON.parse(JSON.stringify(CHART_DEFAULTS));
  cfg.scales.x.title = { display: true, text: xLabel, color: "#8b949e", font: { size: 10 } };
  cfg.scales.y.title = { display: true, text: yLabel, color: "#8b949e", font: { size: 10 } };
  return new Chart(ctx, { type: "line", data: { datasets }, options: cfg });
}

function mkBarChart(canvasId, labels, datasets, yLabel) {
  const ctx = $(canvasId);
  if (!ctx) return null;
  const cfg = JSON.parse(JSON.stringify(CHART_DEFAULTS));
  cfg.plugins.legend = {
    display: true,
    labels: { color: "#8b949e", font: { size: 10 }, boxWidth: 10 }
  };
  cfg.scales.y.title = { display: true, text: yLabel, color: "#8b949e", font: { size: 10 } };
  return new Chart(ctx, {
    type: "bar",
    data: { labels, datasets },
    options: { ...cfg, scales: { ...cfg.scales, x: { ...cfg.scales.x, ticks: { color: "#8b949e", font: { size: 9 } } } } }
  });
}

function destroyChart(c) { if (c) c.destroy(); }

// ── Render results into charts ────────────────────────────────
function renderResults(data) {
  lastResults = data;

  data.results.forEach(res => {
    const key = Object.keys(state.exercises).find(k =>
      state.exercises[k].name === res.exercise.name
    );
    if (!key) return;

    const bm = res.biomek;
    const tr = res.traditional;
    const muscles = res.exercise.muscles_involved;
    const primaries = muscles.filter(m => m !== "forearm_flexors");
    const angles = bm.angles_deg;

    if (!charts[key]) charts[key] = {};
    destroyChart(charts[key].romact);
    destroyChart(charts[key].romst);
    destroyChart(charts[key].baract);
    destroyChart(charts[key].barst);

    // ── ROM: Muscle activation line chart ──────────────────
    const romActDatasets = [];
    muscles.forEach(m => {
      const color = MUSCLE_COLORS[m] || "#aaa";
      // BioMek solid
      romActDatasets.push({
        label: muscleLabel(m) + " (BioMek)",
        data: bm.activations[m].map((v, i) => ({ x: angles[i], y: +v.toFixed(2) })),
        borderColor: color, backgroundColor: "transparent",
        borderWidth: 2, pointRadius: 0, tension: 0.4,
      });
      // Traditional dashed
      romActDatasets.push({
        label: muscleLabel(m) + " (Traditional)",
        data: tr.activations[m].map((v, i) => ({ x: angles[i], y: +v.toFixed(2) })),
        borderColor: color, backgroundColor: "transparent",
        borderWidth: 1.5, borderDash: [5, 4], pointRadius: 0, tension: 0.4, opacity: 0.4,
      });
    });

    charts[key].romact = mkLineChart(
      `chart-romact-${key}`, romActDatasets,
      `${res.exercise.joint.charAt(0).toUpperCase() + res.exercise.joint.slice(1)} Angle (°)`,
      "Activation (% MVC)"
    );

    // ── ROM: Joint stress line chart ───────────────────────
    const romStDatasets = [];
    Object.keys(bm.stresses).forEach(j => {
      const color = JOINT_COLORS[j] || "#aaa";
      romStDatasets.push({
        label: j.charAt(0).toUpperCase() + j.slice(1) + " (BioMek)",
        data: bm.stresses[j].map((v, i) => ({ x: angles[i], y: +(v/1000).toFixed(2) })),
        borderColor: color, backgroundColor: "transparent",
        borderWidth: 2, pointRadius: 0, tension: 0.4,
      });
      romStDatasets.push({
        label: j.charAt(0).toUpperCase() + j.slice(1) + " (Traditional)",
        data: tr.stresses[j].map((v, i) => ({ x: angles[i], y: +(v/1000).toFixed(2) })),
        borderColor: color, backgroundColor: "transparent",
        borderWidth: 1.5, borderDash: [5, 4], pointRadius: 0, tension: 0.4,
      });
    });

    charts[key].romst = mkLineChart(
      `chart-romst-${key}`, romStDatasets,
      `${res.exercise.joint.charAt(0).toUpperCase() + res.exercise.joint.slice(1)} Angle (°)`,
      "Joint Stress (kPa)"
    );

    // ── Bar: Peak muscle activation ────────────────────────
    const barLabels = muscles.map(muscleLabel);
    charts[key].baract = mkBarChart(
      `chart-baract-${key}`, barLabels,
      [
        {
          label: "Traditional",
          data: muscles.map(m => +(tr.peak_activations[m] || 0).toFixed(1)),
          backgroundColor: muscles.map(m => (MUSCLE_COLORS[m] || "#aaa") + "55"),
          borderColor: muscles.map(m => MUSCLE_COLORS[m] || "#aaa"),
          borderWidth: 1,
        },
        {
          label: "BioMek Device",
          data: muscles.map(m => +(bm.peak_activations[m] || 0).toFixed(1)),
          backgroundColor: muscles.map(m => MUSCLE_COLORS[m] || "#aaa"),
          borderColor: muscles.map(m => MUSCLE_COLORS[m] || "#aaa"),
          borderWidth: 1,
        }
      ],
      "Peak Activation (% MVC)"
    );

    // ── Bar: Peak joint stress ─────────────────────────────
    const joints = Object.keys(bm.peak_stresses);
    const jLabels = joints.map(j => j.charAt(0).toUpperCase() + j.slice(1));
    charts[key].barst = mkBarChart(
      `chart-barst-${key}`, jLabels,
      [
        {
          label: "Traditional",
          data: joints.map(j => +((tr.peak_stresses[j] || 0) / 1000).toFixed(1)),
          backgroundColor: joints.map(j => (JOINT_COLORS[j] || "#aaa") + "55"),
          borderColor: joints.map(j => JOINT_COLORS[j] || "#aaa"),
          borderWidth: 1,
        },
        {
          label: "BioMek Device",
          data: joints.map(j => +((bm.peak_stresses[j] || 0) / 1000).toFixed(1)),
          backgroundColor: joints.map(j => JOINT_COLORS[j] || "#aaa"),
          borderColor: joints.map(j => JOINT_COLORS[j] || "#aaa"),
          borderWidth: 1,
        }
      ],
      "Peak Stress (kPa)"
    );

    // ── Summary table ──────────────────────────────────────
    const tbl = $(`table-${key}`);
    if (tbl) {
      let html = `<thead><tr>
        <th>Metric</th>
        <th>Traditional</th>
        <th>BioMek</th>
        <th>Change</th>
      </tr></thead><tbody>`;

      muscles.forEach(m => {
        const tv = (tr.peak_activations[m] || 0).toFixed(1);
        const dv = (bm.peak_activations[m] || 0).toFixed(1);
        const delta = pct(bm.peak_activations[m], tr.peak_activations[m]);
        const cls = delta > 0 ? "good" : (delta < -5 ? "bad" : "");
        html += `<tr>
          <td style="color:${MUSCLE_COLORS[m]||'#aaa'}">${muscleLabel(m)} activation</td>
          <td class="td-trad">${tv}% MVC</td>
          <td class="td-dev">${dv}% MVC</td>
          <td class="td-delta ${cls}">${fmtPct(delta)}</td>
        </tr>`;
      });

      joints.forEach(j => {
        const tv = ((tr.peak_stresses[j] || 0) / 1000).toFixed(1);
        const dv = ((bm.peak_stresses[j] || 0) / 1000).toFixed(1);
        const delta = pct(bm.peak_stresses[j], tr.peak_stresses[j]);
        const cls = delta > 0 ? "good" : (delta < -5 ? "bad" : "");
        html += `<tr>
          <td style="color:${JOINT_COLORS[j]||'#aaa'}">${j.charAt(0).toUpperCase() + j.slice(1)} stress</td>
          <td class="td-trad">${tv} kPa</td>
          <td class="td-dev">${dv} kPa</td>
          <td class="td-delta ${cls}">${fmtPct(delta)}</td>
        </tr>`;
      });

      html += "</tbody>";
      tbl.innerHTML = html;
    }
  });

  // ── Update hero metrics (average across exercises) ─────────
  updateHeroMetrics(data);
  setLoading(false);
  startAnimation();
}

function updateHeroMetrics(data) {
  let wristRed = [], gripRed = [], elbowRed = [];

  data.results.forEach(res => {
    const wt = res.traditional.peak_stresses.wrist || 1;
    const wd = res.biomek.peak_stresses.wrist || 0;
    wristRed.push(pct(wd, wt));

    const gt = res.traditional.peak_activations.forearm_flexors || 1;
    const gd = res.biomek.peak_activations.forearm_flexors || 0;
    gripRed.push(pct(gd, gt));

    const et = res.traditional.peak_stresses.elbow || 1;
    const ed = res.biomek.peak_stresses.elbow || 0;
    elbowRed.push(pct(ed, et));
  });

  const avg = arr => Math.round(arr.reduce((a, b) => a + b, 0) / arr.length);
  $("m-wrist").textContent  = avg(wristRed) + "%";
  $("m-grip").textContent   = avg(gripRed) + "%";
  $("m-elbow").textContent  = avg(elbowRed) + "%";

  // Equivalent cable weight to match same primary muscle stimulus
  // Primary muscles average ~77% of traditional activation → need 1/0.77 ≈ 1.30× weight
  const equivLbs = Math.round(state.f_cable / 0.77);
  const equivKg  = (equivLbs / 2.2046).toFixed(1);
  $("m-equiv").textContent  = `${equivLbs} lbs (${equivKg} kg)`;
}

// ── Loading state ─────────────────────────────────────────────
function setLoading(on) {
  $("status-text").textContent = on ? "Simulating…" : "Up to date";
  document.querySelectorAll(".loading-overlay").forEach(el => {
    el.classList.toggle("visible", on);
  });
}

// ── Build API payload from state ─────────────────────────────
function buildPayload() {
  const exercises = {};
  Object.keys(state.exercises).forEach(key => {
    const ex = state.exercises[key];
    const primaries = ex.muscles_involved.filter(m => m !== "forearm_flexors");
    const total = primaries.reduce((s, m) => s + (ex.muscle_weights[m] || 0), 0);
    const weights = {};
    primaries.forEach(m => {
      weights[m] = total > 0 ? (ex.muscle_weights[m] || 0) / total : 1 / primaries.length;
    });
    exercises[key] = {
      name: ex.name, joint: ex.joint,
      angle_range_deg: ex.angle_range_deg,
      muscles_involved: ex.muscles_involved,
      muscle_weights: weights,
    };
  });

  return {
    f_cable: state.f_cable * LBS_TO_N,   // lbs → N for simulation engine
    device: {
      pad_from_wrist: state.pad_from_wrist / 100,   // cm → m
      grip_force_fraction: state.grip_force_fraction / 100,
    },
    exercises,
  };
}

// ── Simulate ──────────────────────────────────────────────────
async function simulate() {
  setLoading(true);
  try {
    const resp = await fetch("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildPayload()),
    });
    const json = await resp.json();
    if (json.ok) renderResults(json.data);
    else {
      console.error("Simulation error:", json.error);
      $("status-text").textContent = "Error — check console";
      setLoading(false);
    }
  } catch (e) {
    console.error(e);
    $("status-text").textContent = "Network error";
    setLoading(false);
  }
}

function scheduleSimulate() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(simulate, 280);
}

// ── Wire up global sliders ────────────────────────────────────
function wireSliders() {
  const sl = $("sl-fcable");
  sl.addEventListener("input", () => {
    const v = parseInt(sl.value);
    state.f_cable = v;
    $("lbl-fcable").textContent = fmtWeight(v);
    scheduleSimulate();
  });

  const slPad = $("sl-pad");
  slPad.addEventListener("input", () => {
    const v = parseFloat(slPad.value);
    state.pad_from_wrist = v;
    $("lbl-pad").textContent = `${v} cm`;
    scheduleSimulate();
  });

  const slGrip = $("sl-grip");
  slGrip.addEventListener("input", () => {
    const v = parseInt(slGrip.value);
    state.grip_force_fraction = v;
    $("lbl-grip").textContent = `${v}%`;
    scheduleSimulate();
  });

  $("btn-reset").addEventListener("click", () => {
    state = JSON.parse(JSON.stringify(DEFAULTS));
    // Reset slider DOM
    $("sl-fcable").value = state.f_cable;
    $("lbl-fcable").textContent = fmtWeight(state.f_cable);
    $("sl-pad").value = state.pad_from_wrist;
    $("lbl-pad").textContent = `${state.pad_from_wrist} cm`;
    $("sl-grip").value = state.grip_force_fraction;
    $("lbl-grip").textContent = `${state.grip_force_fraction}%`;
    activeExKey = "standard_curl";
    buildSidebarTabs();
    renderMuscleWeights();
    switchMainTab(activeExKey);
    simulate();
  });

  // Pause / resume animation
  let _animPaused = false;
  $("btn-anim-toggle").addEventListener("click", () => {
    _animPaused = !_animPaused;
    if (_animPaused) {
      stopAnimation();
      $("btn-anim-toggle").textContent = "▶ Resume";
    } else {
      startAnimation();
      $("btn-anim-toggle").textContent = "⏸ Pause";
    }
  });

  $("btn-reset").addEventListener("mouseenter", () => {
    $("btn-reset").style.borderColor = "var(--green)";
    $("btn-reset").style.color = "var(--green-lit)";
  });
  $("btn-reset").addEventListener("mouseleave", () => {
    $("btn-reset").style.borderColor = "var(--border)";
    $("btn-reset").style.color = "var(--text-muted)";
  });
}

// ── Boot ──────────────────────────────────────────────────────
function init() {
  buildSidebarTabs();
  renderMuscleWeights();
  buildMainPanels();
  wireSliders();
  simulate();
}

document.addEventListener("DOMContentLoaded", init);
