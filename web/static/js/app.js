/* ============================================================
   BioMek Simulation — Frontend (arm26 / Holzbaur 2005 physics)
   ============================================================ */
'use strict';

const LBS_TO_N = 4.4482;

function fmtWeight(lbs) {
  return `${lbs} lbs (${(lbs / 2.2046).toFixed(1)} kg)`;
}

// ── arm26 muscle metadata ────────────────────────────────────
const MUSCLE_META = {
  BIClong:   { label: "Biceps Long Head",     color: "#e74c3c", role: "flexor"   },
  BICshort:  { label: "Biceps Short Head",    color: "#c0392b", role: "flexor"   },
  BRA:       { label: "Brachialis",           color: "#e67e22", role: "flexor"   },
  TRIlong:   { label: "Triceps Long Head",    color: "#3498db", role: "extensor" },
  TRIlat:    { label: "Triceps Lateral Head", color: "#2980b9", role: "extensor" },
  TRImed:    { label: "Triceps Medial Head",  color: "#1abc9c", role: "extensor" },
  DELT_lat:  { label: "Deltoid Lateral",      color: "#3498db", role: "abductor" },
  DELT_ant:  { label: "Deltoid Anterior",     color: "#2980b9", role: "abductor" },
  SUPSP:     { label: "Supraspinatus",        color: "#8e44ad", role: "abductor" },
  grip:      { label: "Grip (Forearm Flex.)", color: "#95a5a6", role: "grip"     },
};

const JOINT_COLORS = {
  wrist:              "#f85149",
  elbow:              "#d29922",
  shoulder:           "#388bfd",
  medial_epicondyle:  "#a855f7",   // purple — golfer's elbow
  lateral_epicondyle: "#ec4899",   // pink   — tennis elbow
};

const JOINT_LABELS = {
  wrist:              "Wrist",
  elbow:              "Elbow",
  shoulder:           "Shoulder",
  medial_epicondyle:  "Medial Epicondyle (Golfer's)",
  lateral_epicondyle: "Lateral Epicondyle (Tennis)",
};

// ── Defaults ─────────────────────────────────────────────────
const DEFAULTS = {
  f_cable_lbs: 11,
  pad_from_wrist: 2,       // cm
  grip_force_fraction: 5,  // %
  exercises: {
    standard_curl: {
      name: "Standard Curl", joint: "elbow", grip_fmax: 600,
      angle_range_deg: [10, 140], grip_pattern: "supinated",
      muscles: ["BIClong", "BICshort", "BRA", "TRIlong", "TRIlat", "TRImed"],
    },
    reverse_curl: {
      name: "Reverse Curl", joint: "elbow", grip_fmax: 600,
      angle_range_deg: [10, 140], grip_pattern: "pronated",
      muscles: ["BIClong", "BICshort", "BRA", "TRIlong", "TRIlat", "TRImed"],
    },
    lateral_raise: {
      name: "Lateral Raise", joint: "shoulder", grip_fmax: 600,
      angle_range_deg: [5, 90], grip_pattern: "neutral",
      muscles: ["DELT_lat", "DELT_ant", "SUPSP"],
    },
  }
};

let state = JSON.parse(JSON.stringify(DEFAULTS));
let activeExKey = "standard_curl";
let charts = {};
let debounceTimer = null;
let lastResults = null;

const $ = id => document.getElementById(id);

function pct(dev, trad) {
  if (!trad) return 0;
  return Math.round((1 - dev / trad) * 100);
}

function fmtPct(v) {
  if (v === null || isNaN(v)) return "—";
  return (v > 0 ? "-" : "+") + Math.abs(v) + "%";
}

function activeMuscles(key) {
  return state.exercises[key].muscles.filter(m => {
    const r = MUSCLE_META[m]?.role;
    return r === "flexor" || r === "abductor";
  });
}

// ── Exercise tab strip (sidebar) ─────────────────────────────
function buildSidebarTabs() {
  const container = $("ex-tabs");
  container.innerHTML = "";
  Object.keys(state.exercises).forEach(key => {
    const btn = document.createElement("button");
    btn.className = "ex-tab" + (key === activeExKey ? " active" : "");
    btn.textContent = state.exercises[key].name;
    btn.onclick = () => { activeExKey = key; refreshSidebarTabs(); renderMuscleInfo(); };
    container.appendChild(btn);
  });
}

function refreshSidebarTabs() {
  document.querySelectorAll(".ex-tab").forEach((btn, i) => {
    btn.classList.toggle("active", Object.keys(state.exercises)[i] === activeExKey);
  });
}

// ── Muscle info panel (read-only — optimizer determines weights) ─
function renderMuscleInfo() {
  const section = $("muscle-info-section");
  if (!section) return;
  section.innerHTML = "";

  const active = activeMuscles(activeExKey);
  active.forEach(m => {
    const meta = MUSCLE_META[m] || {};
    const row = document.createElement("div");
    row.style.cssText = "display:flex;align-items:center;gap:8px;padding:4px 0;font-size:11px;";
    row.innerHTML = `
      <div style="width:10px;height:10px;border-radius:50%;background:${meta.color};flex-shrink:0;"></div>
      <span style="color:var(--text)">${meta.label}</span>
      <span style="margin-left:auto;color:var(--text-muted);font-size:10px;">
        ${_fmax(m)} N Fmax
      </span>`;
    section.appendChild(row);
  });
}

const ARM26_FMAX = {
  BIClong:624.3, BICshort:435.56, BRA:987.26,
  TRIlong:798.52, TRIlat:624.3, TRImed:624.3,
  DELT_lat:1142.6, DELT_ant:1218.9, SUPSP:487.8
};
function _fmax(m) { return ARM26_FMAX[m] ? ARM26_FMAX[m].toFixed(0) : "—"; }

// ── Main exercise tab strip + panels ─────────────────────────
function buildMainPanels() {
  const strip = $("main-ex-strip");
  const panels = $("exercise-panels");
  strip.innerHTML = ""; panels.innerHTML = "";

  Object.keys(state.exercises).forEach(key => {
    const ex = state.exercises[key];

    const tab = document.createElement("button");
    tab.className = "ex-strip-tab" + (key === activeExKey ? " active" : "");
    tab.textContent = ex.name;
    tab.dataset.key = key;
    tab.onclick = () => switchMainTab(key);
    strip.appendChild(tab);

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
        <div style="padding:14px 18px 6px;font-size:11px;font-weight:600;color:var(--text-muted);
                    text-transform:uppercase;letter-spacing:0.5px;">
          Full Comparison Table
          <span style="font-size:9px;font-weight:400;color:#555;margin-left:8px;text-transform:none;">
            Static optimization · Thelen2003 muscle model · arm26.osim (Holzbaur 2005)
          </span>
        </div>
        <table class="summary-table" id="table-${key}"></table>
      </div>`;
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
  renderMuscleInfo();
  _animAngle = state.exercises[key]?.angle_range_deg?.[0] ?? 10;
  _animDir   = 1;
  startAnimation();
}

// ── Chart config ──────────────────────────────────────────────
const CHART_DEFAULTS = {
  responsive: true, maintainAspectRatio: false,
  animation: { duration: 300 },
  plugins: {
    legend: { display: false },
    tooltip: { backgroundColor:"#161b22", borderColor:"#30363d", borderWidth:1,
               titleColor:"#e6edf3", bodyColor:"#8b949e" }
  },
  scales: {
    x: { grid:{color:"rgba(48,54,61,0.5)"}, ticks:{color:"#8b949e", font:{size:10}} },
    y: { grid:{color:"rgba(48,54,61,0.5)"}, ticks:{color:"#8b949e", font:{size:10}} }
  }
};

function mkLineChart(canvasId, datasets, xLabel, yLabel) {
  const ctx = $(canvasId); if (!ctx) return null;
  const cfg = JSON.parse(JSON.stringify(CHART_DEFAULTS));
  cfg.scales.x.title = { display:true, text:xLabel, color:"#8b949e", font:{size:10} };
  cfg.scales.y.title = { display:true, text:yLabel, color:"#8b949e", font:{size:10} };
  return new Chart(ctx, { type:"line", data:{datasets}, options:cfg });
}

function mkBarChart(canvasId, labels, datasets, yLabel) {
  const ctx = $(canvasId); if (!ctx) return null;
  const cfg = JSON.parse(JSON.stringify(CHART_DEFAULTS));
  cfg.plugins.legend = { display:true, labels:{color:"#8b949e",font:{size:10},boxWidth:10} };
  cfg.scales.y.title = { display:true, text:yLabel, color:"#8b949e", font:{size:10} };
  return new Chart(ctx, { type:"bar", data:{labels,datasets}, options:cfg });
}

function destroyChart(c) { if (c) c.destroy(); }

// ── Render results ────────────────────────────────────────────
function renderResults(data) {
  lastResults = data;

  data.results.forEach(res => {
    const key = Object.keys(state.exercises).find(k =>
      state.exercises[k].name === res.exercise.name);
    if (!key) return;

    const bm = res.biomek, tr = res.traditional;
    const allMuscles = res.exercise.muscles;
    const primaryMuscles = allMuscles.filter(m => MUSCLE_META[m]?.role !== "extensor");
    const displayMuscles = [...primaryMuscles, "grip"];
    const angles = bm.angles_deg;

    if (!charts[key]) charts[key] = {};
    ["romact","romst","baract","barst"].forEach(n => destroyChart(charts[key][n]));

    // ROM: muscle activation
    const romActDs = [];
    displayMuscles.forEach(m => {
      const color = MUSCLE_META[m]?.color || "#aaa";
      romActDs.push({ label: (MUSCLE_META[m]?.label||m)+" (BioMek)",
        data: bm.activations[m].map((v,i) => ({x:angles[i],y:+v.toFixed(2)})),
        borderColor:color, backgroundColor:"transparent", borderWidth:2, pointRadius:0, tension:0.4 });
      romActDs.push({ label: (MUSCLE_META[m]?.label||m)+" (Traditional)",
        data: tr.activations[m].map((v,i) => ({x:angles[i],y:+v.toFixed(2)})),
        borderColor:color, backgroundColor:"transparent", borderWidth:1.5,
        borderDash:[5,4], pointRadius:0, tension:0.4 });
    });
    charts[key].romact = mkLineChart(`chart-romact-${key}`, romActDs,
      `${res.exercise.joint.charAt(0).toUpperCase()+res.exercise.joint.slice(1)} Angle (°)`,
      "Activation (% MVC)");

    // ROM: joint stress
    const romStDs = [];
    Object.keys(bm.stresses).forEach(j => {
      const color = JOINT_COLORS[j] || "#aaa";
      romStDs.push({ label: j.charAt(0).toUpperCase()+j.slice(1)+" (BioMek)",
        data: bm.stresses[j].map((v,i) => ({x:angles[i],y:+(v/1000).toFixed(2)})),
        borderColor:color, backgroundColor:"transparent", borderWidth:2, pointRadius:0, tension:0.4 });
      romStDs.push({ label: j.charAt(0).toUpperCase()+j.slice(1)+" (Traditional)",
        data: tr.stresses[j].map((v,i) => ({x:angles[i],y:+(v/1000).toFixed(2)})),
        borderColor:color, backgroundColor:"transparent", borderWidth:1.5,
        borderDash:[5,4], pointRadius:0, tension:0.4 });
    });
    charts[key].romst = mkLineChart(`chart-romst-${key}`, romStDs,
      `${res.exercise.joint.charAt(0).toUpperCase()+res.exercise.joint.slice(1)} Angle (°)`,
      "Joint Stress (kPa)");

    // Bar: peak muscle activation
    const barLabels = displayMuscles.map(m => MUSCLE_META[m]?.label || m);
    charts[key].baract = mkBarChart(`chart-baract-${key}`, barLabels, [
      { label:"Traditional",
        data: displayMuscles.map(m => +(tr.peak_activations[m]||0).toFixed(1)),
        backgroundColor: displayMuscles.map(m => (MUSCLE_META[m]?.color||"#aaa")+"55"),
        borderColor:     displayMuscles.map(m => MUSCLE_META[m]?.color||"#aaa"), borderWidth:1 },
      { label:"BioMek Device",
        data: displayMuscles.map(m => +(bm.peak_activations[m]||0).toFixed(1)),
        backgroundColor: displayMuscles.map(m => MUSCLE_META[m]?.color||"#aaa"),
        borderColor:     displayMuscles.map(m => MUSCLE_META[m]?.color||"#aaa"), borderWidth:1 },
    ], "Peak Activation (% MVC)");

    // Bar: peak joint stress — show all joints including epicondyles
    const joints = Object.keys(bm.peak_stresses);
    charts[key].barst = mkBarChart(`chart-barst-${key}`,
      joints.map(j => JOINT_LABELS[j] || j), [
      { label:"Traditional",
        data: joints.map(j => +((tr.peak_stresses[j]||0)/1000).toFixed(1)),
        backgroundColor: joints.map(j => (JOINT_COLORS[j]||"#aaa")+"55"),
        borderColor:     joints.map(j => JOINT_COLORS[j]||"#aaa"), borderWidth:1 },
      { label:"BioMek Device",
        data: joints.map(j => +((bm.peak_stresses[j]||0)/1000).toFixed(1)),
        backgroundColor: joints.map(j => JOINT_COLORS[j]||"#aaa"),
        borderColor:     joints.map(j => JOINT_COLORS[j]||"#aaa"), borderWidth:1 },
    ], "Peak Stress (kPa)");

    // Summary table
    const tbl = $(`table-${key}`);
    if (tbl) {
      let html = `<thead><tr><th>Metric</th><th>Traditional</th><th>BioMek</th><th>Change</th></tr></thead><tbody>`;
      displayMuscles.forEach(m => {
        const tv = (tr.peak_activations[m]||0).toFixed(1);
        const dv = (bm.peak_activations[m]||0).toFixed(1);
        const delta = pct(bm.peak_activations[m], tr.peak_activations[m]);
        const cls = delta > 0 ? "good" : (delta < -5 ? "bad" : "");
        html += `<tr>
          <td style="color:${MUSCLE_META[m]?.color||'#aaa'}">${MUSCLE_META[m]?.label||m}</td>
          <td class="td-trad">${tv}% MVC</td><td class="td-dev">${dv}% MVC</td>
          <td class="td-delta ${cls}">${fmtPct(delta)}</td></tr>`;
      });
      joints.forEach(j => {
        const tv = ((tr.peak_stresses[j]||0)/1000).toFixed(1);
        const dv = ((bm.peak_stresses[j]||0)/1000).toFixed(1);
        const delta = pct(bm.peak_stresses[j], tr.peak_stresses[j]);
        const cls = delta > 0 ? "good" : (delta < -5 ? "bad" : "");
        const jLabel = JOINT_LABELS[j] || j.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
        html += `<tr>
          <td style="color:${JOINT_COLORS[j]||'#aaa'}">${jLabel}</td>
          <td class="td-trad">${tv} kPa</td><td class="td-dev">${dv} kPa</td>
          <td class="td-delta ${cls}">${fmtPct(delta)}</td></tr>`;
      });
      tbl.innerHTML = html + "</tbody>";
    }
  });

  updateHeroMetrics(data);
  setLoading(false);
  startAnimation();
}

function updateHeroMetrics(data) {
  let wristRed = [], gripRed = [], elbowRed = [], epicRed = [];

  data.results.forEach(res => {
    const wt = res.traditional.peak_stresses.wrist || 1;
    wristRed.push(pct(res.biomek.peak_stresses.wrist, wt));
    const gt = res.traditional.peak_activations.grip || 1;
    gripRed.push(pct(res.biomek.peak_activations.grip, gt));
    const et = res.traditional.peak_stresses.elbow || 1;
    elbowRed.push(pct(res.biomek.peak_stresses.elbow, et));
    // Epicondyle: take whichever is higher (medial vs lateral) as primary indicator
    const mt = res.traditional.peak_stresses.medial_epicondyle || 0;
    const lt = res.traditional.peak_stresses.lateral_epicondyle || 0;
    if (mt > 0 || lt > 0) {
      const epicT = Math.max(mt, lt);
      const epicB = Math.max(res.biomek.peak_stresses.medial_epicondyle || 0,
                             res.biomek.peak_stresses.lateral_epicondyle || 0);
      epicRed.push(pct(epicB, epicT));
    }
  });

  const avg = arr => arr.length ? Math.round(arr.reduce((a,b)=>a+b,0)/arr.length) : 0;
  $("m-wrist").textContent = avg(wristRed) + "%";
  $("m-grip").textContent  = avg(gripRed)  + "%";
  $("m-elbow").textContent = avg(elbowRed) + "%";
  if ($("m-epic")) $("m-epic").textContent = avg(epicRed) + "%";

  const equivLbs = Math.round(state.f_cable_lbs / 0.77);
  $("m-equiv").textContent = fmtWeight(equivLbs);
}

// ── Loading ───────────────────────────────────────────────────
function setLoading(on) {
  $("status-text").textContent = on ? "Simulating…" : "Up to date";
  document.querySelectorAll(".loading-overlay").forEach(el => {
    el.classList.toggle("visible", on);
  });
}

// ── Build API payload ─────────────────────────────────────────
function buildPayload() {
  const exercises = {};
  Object.keys(state.exercises).forEach(key => {
    const ex = state.exercises[key];
    exercises[key] = {
      name: ex.name, joint: ex.joint,
      angle_range_deg: ex.angle_range_deg,
      muscles: ex.muscles,
      grip_fmax: ex.grip_fmax || 600,
      grip_pattern: ex.grip_pattern || "neutral",
    };
  });
  return {
    f_cable_lbs: state.f_cable_lbs,
    n_rom_points: 60,
    device: {
      pad_from_wrist:       state.pad_from_wrist / 100,
      grip_force_fraction:  state.grip_force_fraction / 100,
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
      console.error("Simulation error:", json.error, json.trace);
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

// ── Wire sliders ──────────────────────────────────────────────
function wireSliders() {
  const sl = $("sl-fcable");
  sl.addEventListener("input", () => {
    state.f_cable_lbs = parseInt(sl.value);
    $("lbl-fcable").textContent = fmtWeight(state.f_cable_lbs);
    scheduleSimulate();
  });

  const slPad = $("sl-pad");
  slPad.addEventListener("input", () => {
    state.pad_from_wrist = parseFloat(slPad.value);
    $("lbl-pad").textContent = `${state.pad_from_wrist} cm`;
    scheduleSimulate();
  });

  const slGrip = $("sl-grip");
  slGrip.addEventListener("input", () => {
    state.grip_force_fraction = parseInt(slGrip.value);
    $("lbl-grip").textContent = `${state.grip_force_fraction}%`;
    scheduleSimulate();
  });

  // Pause/resume animation
  let _animPaused = false;
  $("btn-anim-toggle").addEventListener("click", () => {
    _animPaused = !_animPaused;
    if (_animPaused) { stopAnimation(); $("btn-anim-toggle").textContent = "▶ Resume"; }
    else             { startAnimation(); $("btn-anim-toggle").textContent = "⏸ Pause"; }
  });

  $("btn-reset").addEventListener("click", () => {
    state = JSON.parse(JSON.stringify(DEFAULTS));
    $("sl-fcable").value = state.f_cable_lbs;
    $("lbl-fcable").textContent = fmtWeight(state.f_cable_lbs);
    $("sl-pad").value = state.pad_from_wrist;
    $("lbl-pad").textContent = `${state.pad_from_wrist} cm`;
    $("sl-grip").value = state.grip_force_fraction;
    $("lbl-grip").textContent = `${state.grip_force_fraction}%`;
    activeExKey = "standard_curl";
    buildSidebarTabs(); renderMuscleInfo(); switchMainTab(activeExKey);
    simulate();
  });

  const btn = $("btn-reset");
  btn.addEventListener("mouseenter", () => { btn.style.borderColor="var(--green)"; btn.style.color="var(--green-lit)"; });
  btn.addEventListener("mouseleave", () => { btn.style.borderColor="var(--border)"; btn.style.color="var(--text-muted)"; });
}

// ── Boot ──────────────────────────────────────────────────────
function init() {
  buildSidebarTabs();
  renderMuscleInfo();
  buildMainPanels();
  wireSliders();
  simulate();
}

document.addEventListener("DOMContentLoaded", init);
