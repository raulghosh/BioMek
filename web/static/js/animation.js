/* ============================================================
   BioMek Motion Simulation — Canvas Animation
   Reads lastResults + state + activeExKey from app.js globals
   ============================================================ */
'use strict';

// ── Segment lengths in canvas pixels ─────────────────────────
const PX = { upperArm: 88, forearm: 72, hand: 26 };

// ── Animation state ───────────────────────────────────────────
let _animId    = null;
let _animAngle = 10;
let _animDir   = 1;
const INTERVAL_MS      = 50;   // 20fps — keeps browser idle enough for screenshots
const SPEED_DEG_PER_TICK = INTERVAL_MS / 1000 * 28;

// ── roundRect polyfill (not available in all preview browsers) ─
function _roundRect(ctx, x, y, w, h, r) {
  r = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.arcTo(x + w, y,     x + w, y + r,     r);
  ctx.lineTo(x + w, y + h - r);
  ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
  ctx.lineTo(x + r, y + h);
  ctx.arcTo(x,     y + h, x,     y + h - r, r);
  ctx.lineTo(x, y + r);
  ctx.arcTo(x,     y,     x + r, y,         r);
  ctx.closePath();
}

// ── Public entry points ───────────────────────────────────────
function startAnimation() {
  if (_animId) clearInterval(_animId);
  _animId = setInterval(_tick, INTERVAL_MS);
}

function stopAnimation() {
  if (_animId) clearInterval(_animId);
  _animId = null;
}

function _tick() {
  const ex = state?.exercises?.[activeExKey];
  if (ex) {
    const [aMin, aMax] = ex.angle_range_deg;
    _animAngle += _animDir * SPEED_DEG_PER_TICK;
    if (_animAngle >= aMax) { _animAngle = aMax; _animDir = -1; }
    if (_animAngle <= aMin) { _animAngle = aMin; _animDir =  1; }
  }

  _drawPanel('anim-trad',   'traditional', _animAngle);
  _drawPanel('anim-biomek', 'biomek',      _animAngle);
}

// ── Interpolation helper ──────────────────────────────────────
function _lerp(arr, angles, target) {
  if (!arr?.length || !angles?.length) return 0;
  const n = angles.length;
  if (target <= angles[0])   return arr[0];
  if (target >= angles[n-1]) return arr[n-1];
  for (let i = 0; i < n - 1; i++) {
    if (angles[i] <= target && target <= angles[i+1]) {
      const t = (target - angles[i]) / (angles[i+1] - angles[i]);
      return arr[i] * (1 - t) + arr[i+1] * t;
    }
  }
  return arr[n-1];
}

// ── Stress → colour (green → yellow → red) ───────────────────
function _stressColor(f) {
  f = Math.max(0, Math.min(1, f));
  let r, g, b;
  if (f < 0.5) {
    const t = f * 2;
    r = Math.round(46  + (210 - 46)  * t);
    g = Math.round(160 + (153 - 160) * t);
    b = Math.round(67  + (34  - 67)  * t);
  } else {
    const t = (f - 0.5) * 2;
    r = Math.round(210 + (248 - 210) * t);
    g = Math.round(153 + (81  - 153) * t);
    b = Math.round(34  + (73  - 34)  * t);
  }
  return `rgb(${r},${g},${b})`;
}

// ── Main draw dispatcher ──────────────────────────────────────
function _drawPanel(canvasId, mode, angleDeg) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;

  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#0d1117';
  ctx.fillRect(0, 0, W, H);

  // Gather simulation data
  const exName  = state?.exercises?.[activeExKey]?.name;
  const allRes  = lastResults?.results;
  const resObj  = allRes?.find(r => r.exercise.name === exName);
  const data    = resObj?.[mode];
  const tradRef = resObj?.traditional;
  const angles  = data?.angles_deg;

  const wristS    = _lerp(data?.stresses?.wrist,    angles, angleDeg);
  const elbowS    = _lerp(data?.stresses?.elbow,    angles, angleDeg);
  const shoulderS = _lerp(data?.stresses?.shoulder, angles, angleDeg);
  const gripAct   = _lerp(data?.activations?.forearm_flexors, angles, angleDeg);

  const maxWrist    = tradRef?.peak_stresses?.wrist    || 1;
  const maxElbow    = tradRef?.peak_stresses?.elbow    || 1;
  const maxShoulder = tradRef?.peak_stresses?.shoulder || 1;
  const maxGrip     = tradRef?.peak_activations?.forearm_flexors || 1;

  const ex       = state?.exercises?.[activeExKey];
  const isLateral = ex?.joint === 'shoulder';

  if (isLateral) {
    _drawLateral(ctx, W, H, angleDeg, mode,
      wristS / maxWrist, elbowS / maxElbow, shoulderS / maxShoulder, gripAct / maxGrip,
      wristS, elbowS, shoulderS, gripAct);
  } else {
    _drawCurl(ctx, W, H, angleDeg, mode,
      wristS / maxWrist, elbowS / maxElbow, gripAct / maxGrip,
      wristS, elbowS, gripAct);
  }

  // Top label
  const label = mode === 'biomek' ? 'BioMek Device' : 'Traditional Handle';
  const lcolor = mode === 'biomek' ? '#3fb950' : '#8b949e';
  ctx.font = 'bold 12px -apple-system,sans-serif';
  ctx.textAlign = 'center';
  ctx.fillStyle = lcolor;
  ctx.fillText(label, W / 2, 20);

  // Bottom angle readout
  ctx.font = '10px -apple-system,sans-serif';
  ctx.fillStyle = '#555';
  ctx.textAlign = 'center';
  ctx.fillText(`${Math.round(angleDeg)}°`, W / 2, H - 6);
}

// ── Curl (elbow) drawing ──────────────────────────────────────
function _drawCurl(ctx, W, H, angleDeg, mode,
    wristFrac, elbowFrac, gripFrac,
    wristS, elbowS, gripAct) {

  const aRad = angleDeg * Math.PI / 180;

  // Skeleton geometry
  const shoulder = { x: W / 2 + 8, y: 44 };
  const elbow    = { x: shoulder.x, y: shoulder.y + PX.upperArm };

  const fDx = -Math.sin(aRad) * PX.forearm;
  const fDy =  Math.cos(aRad) * PX.forearm;
  const wrist = { x: elbow.x + fDx, y: elbow.y + fDy };

  const hDx = -Math.sin(aRad) * PX.hand;
  const hDy =  Math.cos(aRad) * PX.hand;
  const handTip = { x: wrist.x + hDx, y: wrist.y + hDy };

  // Pad sits ~12% of forearm length from wrist toward elbow
  const pad = {
    x: wrist.x - fDx * 0.12,
    y: wrist.y - fDy * 0.12,
  };

  const forcePoint = mode === 'biomek' ? pad : handTip;
  const pulley = { x: W / 2 - 20, y: H - 28 };

  _cable(ctx, forcePoint, pulley);
  _forceArrow(ctx, forcePoint, pulley, mode);

  // Arm segments
  _segment(ctx, shoulder, elbow,   14);
  _segment(ctx, elbow,    wrist,   11);
  _segment(ctx, wrist, handTip, mode === 'traditional' ? 8 : 5, mode === 'biomek' ? 0.35 : 1);

  // Force application indicator
  if (mode === 'traditional') {
    _indicator(ctx, handTip, '#e74c3c', 'Grip', 'right');
  } else {
    _padRect(ctx, wrist, pad, '#3fb950');
    _indicator(ctx, pad, '#3fb950', 'Pad', 'left');
  }

  // Joints
  _joint(ctx, shoulder, 9,  0,         null,   false);
  _joint(ctx, elbow,    11, elbowFrac, `${(elbowS/1000).toFixed(0)} kPa`, 'left');
  _joint(ctx, wrist,    9,  wristFrac, `${(wristS/1000).toFixed(0)} kPa`, 'left');

  // Grip bar
  _activationBar(ctx, W - 14, H - 30, 10, 55, gripFrac, `${gripAct.toFixed(0)}%`, 'Grip');
}

// ── Lateral raise (shoulder) drawing ─────────────────────────
function _drawLateral(ctx, W, H, angleDeg, mode,
    wristFrac, elbowFrac, shoulderFrac, gripFrac,
    wristS, elbowS, shoulderS, gripAct) {

  const aRad = angleDeg * Math.PI / 180;
  const shoulder = { x: 52, y: H / 2 + 20 };

  const coA = Math.cos(aRad), siA = Math.sin(aRad);
  const elbow = {
    x: shoulder.x + PX.upperArm * coA,
    y: shoulder.y - PX.upperArm * siA,
  };
  const wrist = {
    x: elbow.x + PX.forearm * coA,
    y: elbow.y - PX.forearm * siA,
  };
  const handTip = {
    x: wrist.x + PX.hand * coA,
    y: wrist.y - PX.hand * siA,
  };

  const pad = {
    x: wrist.x + 0.12 * (elbow.x - wrist.x),
    y: wrist.y + 0.12 * (elbow.y - wrist.y),
  };

  const forcePoint = mode === 'biomek' ? pad : handTip;
  const pulley = { x: W - 22, y: H - 22 };

  _cable(ctx, forcePoint, pulley);
  _forceArrow(ctx, forcePoint, pulley, mode);

  _segment(ctx, shoulder, elbow,   14);
  _segment(ctx, elbow,    wrist,   11);
  _segment(ctx, wrist, handTip, mode === 'traditional' ? 8 : 5, mode === 'biomek' ? 0.35 : 1);

  if (mode === 'traditional') {
    _indicator(ctx, handTip, '#e74c3c', 'Grip', 'right');
  } else {
    _padRect(ctx, wrist, pad, '#3fb950');
    _indicator(ctx, pad, '#3fb950', 'Pad', 'above');
  }

  _joint(ctx, shoulder, 12, shoulderFrac, `${(shoulderS/1000).toFixed(0)} kPa`, 'below');
  _joint(ctx, elbow,    10, elbowFrac,   `${(elbowS/1000).toFixed(0)} kPa`,   'above');
  _joint(ctx, wrist,     8, wristFrac,   `${(wristS/1000).toFixed(0)} kPa`,   'above');

  _activationBar(ctx, W - 14, H - 30, 10, 55, gripFrac, `${gripAct.toFixed(0)}%`, 'Grip');
}

// ── Drawing primitives ────────────────────────────────────────
function _segment(ctx, p1, p2, width, alpha = 1) {
  ctx.save();
  ctx.globalAlpha = alpha;
  const grad = ctx.createLinearGradient(p1.x, p1.y, p2.x, p2.y);
  grad.addColorStop(0,   '#1e293b');
  grad.addColorStop(0.5, '#475569');
  grad.addColorStop(1,   '#1e293b');
  ctx.strokeStyle = grad;
  ctx.lineWidth   = width;
  ctx.lineCap     = 'round';
  ctx.beginPath();
  ctx.moveTo(p1.x, p1.y);
  ctx.lineTo(p2.x, p2.y);
  ctx.stroke();
  ctx.restore();
}

function _joint(ctx, pos, baseR, frac, label, side) {
  const color = _stressColor(frac);
  const glowR = baseR + frac * 14;

  // Outer glow
  ctx.save();
  ctx.shadowColor = color;
  ctx.shadowBlur  = 4 + frac * 20;
  ctx.fillStyle   = color;
  ctx.globalAlpha = 0.55 + frac * 0.45;
  ctx.beginPath();
  ctx.arc(pos.x, pos.y, glowR, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();

  // Core white dot
  ctx.fillStyle = '#e2e8f0';
  ctx.beginPath();
  ctx.arc(pos.x, pos.y, baseR * 0.38, 0, Math.PI * 2);
  ctx.fill();

  // Label
  if (label && side) {
    ctx.font = 'bold 9px -apple-system,sans-serif';
    ctx.fillStyle = color;
    if (side === 'left') {
      ctx.textAlign = 'right';
      ctx.fillText(label, pos.x - glowR - 2, pos.y + 3);
    } else if (side === 'right') {
      ctx.textAlign = 'left';
      ctx.fillText(label, pos.x + glowR + 2, pos.y + 3);
    } else if (side === 'above') {
      ctx.textAlign = 'center';
      ctx.fillText(label, pos.x, pos.y - glowR - 3);
    } else if (side === 'below') {
      ctx.textAlign = 'center';
      ctx.fillText(label, pos.x, pos.y + glowR + 10);
    }
  }
}

function _cable(ctx, from, to) {
  const mx = (from.x + to.x) / 2 + (from.x > to.x ? -12 : 12);
  const my = (from.y + to.y) / 2;
  ctx.save();
  ctx.strokeStyle = '#4a5568';
  ctx.lineWidth   = 1.5;
  ctx.setLineDash([5, 4]);
  ctx.beginPath();
  ctx.moveTo(from.x, from.y);
  ctx.quadraticCurveTo(mx, my, to.x, to.y);
  ctx.stroke();
  ctx.setLineDash([]);
  // Pulley
  ctx.strokeStyle = '#64748b';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(to.x, to.y, 5, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();
}

function _forceArrow(ctx, from, to, mode) {
  const color = mode === 'biomek' ? '#3fb950' : '#e74c3c';
  const dir   = Math.atan2(to.y - from.y, to.x - from.x);
  const len   = 24;
  const ex = from.x + Math.cos(dir) * len;
  const ey = from.y + Math.sin(dir) * len;

  ctx.save();
  ctx.shadowColor = color;
  ctx.shadowBlur  = 10;
  ctx.strokeStyle = color;
  ctx.fillStyle   = color;
  ctx.lineWidth   = 2;

  ctx.beginPath();
  ctx.moveTo(from.x, from.y);
  ctx.lineTo(ex, ey);
  ctx.stroke();

  // Arrowhead
  const h = 7, s = 0.38;
  ctx.beginPath();
  ctx.moveTo(ex, ey);
  ctx.lineTo(ex - h * Math.cos(dir - s), ey - h * Math.sin(dir - s));
  ctx.lineTo(ex - h * Math.cos(dir + s), ey - h * Math.sin(dir + s));
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

function _indicator(ctx, pos, color, label, side) {
  ctx.save();
  ctx.shadowColor = color;
  ctx.shadowBlur  = 14;
  ctx.fillStyle   = color;
  ctx.beginPath();
  ctx.arc(pos.x, pos.y, 6, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();

  ctx.font      = 'bold 9px -apple-system,sans-serif';
  ctx.fillStyle = color;
  if (side === 'right') { ctx.textAlign = 'left';  ctx.fillText(label, pos.x + 10, pos.y - 6); }
  if (side === 'left')  { ctx.textAlign = 'right'; ctx.fillText(label, pos.x - 10, pos.y - 6); }
  if (side === 'above') { ctx.textAlign = 'center'; ctx.fillText(label, pos.x, pos.y - 12); }
}

function _padRect(ctx, wrist, pad, color) {
  // Draw a small highlighted band to represent the forearm pad
  const dx = pad.x - wrist.x, dy = pad.y - wrist.y;
  const len = Math.sqrt(dx*dx + dy*dy) || 1;
  const nx = -dy / len, ny = dx / len;  // perpendicular
  const w = 5;  // half-width of pad band

  ctx.save();
  ctx.shadowColor = color;
  ctx.shadowBlur  = 10;
  ctx.fillStyle   = color + 'aa';
  ctx.strokeStyle = color;
  ctx.lineWidth   = 1;
  ctx.beginPath();
  ctx.moveTo(wrist.x + nx*w, wrist.y + ny*w);
  ctx.lineTo(wrist.x - nx*w, wrist.y - ny*w);
  ctx.lineTo(pad.x  - nx*w, pad.y  - ny*w);
  ctx.lineTo(pad.x  + nx*w, pad.y  + ny*w);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

function _activationBar(ctx, x, y, w, h, frac, valLabel, titleLabel) {
  frac = Math.max(0, Math.min(1, frac));
  const color = _stressColor(frac);
  const filled = h * frac;

  // Track
  ctx.fillStyle = '#1a2030';
  ctx.strokeStyle = '#30363d';
  ctx.lineWidth = 1;
  _roundRect(ctx, x - w, y - h, w, h, 2);
  ctx.fill();
  ctx.stroke();

  // Fill
  if (filled > 0) {
    ctx.save();
    ctx.shadowColor = color;
    ctx.shadowBlur  = 6 * frac;
    ctx.fillStyle   = color;
    _roundRect(ctx, x - w, y - filled, w, filled, 2);
    ctx.fill();
    ctx.restore();
  }

  // Value
  ctx.font      = 'bold 8px -apple-system,sans-serif';
  ctx.fillStyle = color;
  ctx.textAlign = 'center';
  ctx.fillText(valLabel,    x - w/2, y + 10);
  ctx.fillStyle = '#555';
  ctx.fillText(titleLabel,  x - w/2, y + 19);
}
