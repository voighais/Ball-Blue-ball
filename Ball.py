import os
import webview

SAVE_PATH = os.path.join(os.path.expanduser('~'), '.ball_at_sea.json')


class SaveApi:
    def load(self):
        try:
            with open(SAVE_PATH, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return ''

    def save(self, data):
        try:
            with open(SAVE_PATH, 'w', encoding='utf-8') as f:
                f.write(data)
            return True
        except Exception:
            return False


HTML = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body { margin: 0; padding: 0; overflow: hidden; background: #06111f; cursor: none; }
  canvas { display: block; }
</style>
</head>
<body>
<canvas id="c"></canvas>
<script>
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
let W = 0, H = 0;
function resize() {
  W = canvas.width  = window.innerWidth;
  H = canvas.height = window.innerHeight;
}
window.addEventListener('resize', resize);
resize();

const DIFF = {
  easy:   { speed: 115, spawn: 1.20, label: 'EASY'   },
  normal: { speed: 165, spawn: 0.90, label: 'NORMAL' },
  hard:   { speed: 225, spawn: 0.62, label: 'HARD'   }
};

const SHOP_ITEMS = [
  { id: 'trail_ice',     type: 'trail', name: 'Ice Trail',     price: 150, desc: 'Frozen wake behind your ball' },
  { id: 'hat_pirate',    type: 'hat',   name: 'Pirate Hat',    price: 200, desc: 'A tricorn for true sailors' },
  { id: 'trail_rainbow', type: 'trail', name: 'Rainbow Trail', price: 400, desc: 'A colorful wake' }
];

const SAVE_KEY = 'ballAtSea_v2';
const DEFAULT_SAVE = {
  totalPoints: 0,
  best: 0,
  runs: 0,
  owned:    { trail_ice: false, hat_pirate: false, trail_rainbow: false },
  equipped: { trail: 'default', hat: null },
  difficulty: 'normal'
};

let save = JSON.parse(JSON.stringify(DEFAULT_SAVE));
let saveLoaded = false;
let pendingSaveData = null;

function mergeSave(d) {
  if (!d) return;
  if (typeof d.totalPoints === 'number') save.totalPoints = d.totalPoints;
  if (typeof d.best === 'number')        save.best        = d.best;
  if (typeof d.runs === 'number')        save.runs        = d.runs;
  if (d.owned)    save.owned    = Object.assign(save.owned, d.owned);
  if (d.equipped) save.equipped = Object.assign(save.equipped, d.equipped);
  if (d.difficulty && DIFF[d.difficulty]) {
    save.difficulty = d.difficulty;
    difficulty = d.difficulty;
  }
}

function tryLocalLoad() {
  try {
    const raw = localStorage.getItem(SAVE_KEY);
    if (raw) mergeSave(JSON.parse(raw));
  } catch(e) {}
}

function persistSave() {
  const data = JSON.stringify(save);
  try { localStorage.setItem(SAVE_KEY, data); } catch(e) {}

  if (!saveLoaded) {
    pendingSaveData = data;
    return;
  }
  if (window.pywebview && window.pywebview.api && window.pywebview.api.save) {
    window.pywebview.api.save(data).catch(() => {});
  }
}

tryLocalLoad();

window.addEventListener('pywebviewready', async () => {
  try {
    const raw = await window.pywebview.api.load();
    if (raw) {
      mergeSave(JSON.parse(raw));
    } else {
      persistSave();
    }
  } catch(e) {}
  saveLoaded = true;
  if (pendingSaveData !== null) {
    try { window.pywebview.api.save(pendingSaveData); } catch(e) {}
    pendingSaveData = null;
  }
});

let state = 'menu';
let difficulty = save.difficulty;
let score = 0;
let shakeT = 0;
let newRecord = false;
let runCredited = false;

const ball = { x: 0, y: 0, r: 17, trail: [] };
let obstacles = [];
let mouseX = 0;
let spawnTimer = 0, lastTime = 0, overTimer = 0;
let hitAreas = [];

const rand = (a, b) => a + Math.random() * (b - a);
function roundRect(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y,     x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x,     y + h, r);
  ctx.arcTo(x,     y + h, x,     y,     r);
  ctx.arcTo(x,     y,     x + w, y,     r);
  ctx.closePath();
}

function makeShape(w, h, n, jitter) {
  const pts = [];
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2 - Math.PI / 2;
    const rx = (w / 2) * (1 - jitter + Math.random() * jitter * 2);
    const ry = (h / 2) * (1 - jitter + Math.random() * jitter * 2);
    pts.push([Math.cos(a) * rx, Math.sin(a) * ry]);
  }
  return pts;
}

function makeObstacle() {
  const r = Math.random();
  let type;
  if (r < 0.42)      type = 'rock';
  else if (r < 0.68) type = 'iceberg';
  else if (r < 0.86) type = 'log';
  else               type = 'mine';

  const o = { type, x: 0, y: 0, w: 0, h: 0, vx: 0, spin: 0, angle: 0, speedMul: 1 };

  if (type === 'rock') {
    o.w = rand(55, 95); o.h = rand(50, 80);
    o.shape = makeShape(o.w, o.h, 9, 0.28);
  } else if (type === 'iceberg') {
    o.w = rand(95, 150); o.h = rand(45, 65);
    o.speedMul = 0.72;
    o.shape = makeShape(o.w, o.h, 7, 0.34);
  } else if (type === 'log') {
    o.w = rand(90, 140); o.h = 26;
    o.speedMul = 1.18;
    o.angle = rand(-0.22, 0.22);
  } else {
    o.w = o.h = rand(42, 56);
    o.speedMul = 0.9;
    o.vx = rand(-70, 70);
    o.spin = rand(-1.5, 1.5);
  }
  return o;
}

function wouldOverlap(o) {
  const pad = 30;
  const ax = o.x, ay = -o.h - 20, aw = o.w, ah = o.h;
  for (const other of obstacles) {
    if (ax - pad < other.x + other.w &&
        ax + aw + pad > other.x &&
        ay - pad < other.y + other.h &&
        ay + ah + pad > other.y) return true;
  }
  return false;
}

function spawnObstacle() {
  const o = makeObstacle();
  for (let attempt = 0; attempt < 24; attempt++) {
    o.x = rand(10, Math.max(20, W - o.w - 10));
    if (!wouldOverlap(o)) {
      o.y = -o.h - 20;
      obstacles.push(o);
      return true;
    }
  }
  return false;
}

function startGame() {
  state = 'play';
  score = 0;
  newRecord = false;
  runCredited = false;
  obstacles = [];
  spawnTimer = 0.4;
  ball.x = W / 2;
  ball.y = H - 90;
  ball.trail = [];
  mouseX = ball.x;
}

function commitRun() {
  if (runCredited) return;
  runCredited = true;
  const pts = Math.floor(score);
  if (pts <= 0) return;
  save.totalPoints += pts;
  save.runs += 1;
  if (score > save.best) {
    save.best = score;
    newRecord = true;
  }
  persistSave();
}

function gameOver() {
  state = 'over';
  overTimer = 0;
  shakeT = 0.4;
  commitRun();
}

function update(dt) {
  if (shakeT > 0) shakeT -= dt;

  if (state === 'menu' || state === 'shop') {
    ball.x += (mouseX - ball.x) * Math.min(1, dt * 4);
    ball.y = H - 90 + Math.sin(performance.now() / 700) * 8;
    pushTrail();
    return;
  }

  if (state === 'over') {
    overTimer += dt;
    pushTrail();
    for (const o of obstacles) o.y += (o.speed || 150) * dt * 0.25;
    obstacles = obstacles.filter(o => o.y < H + 150);
    return;
  }

  ball.x += (mouseX - ball.x) * Math.min(1, dt * 9);
  ball.x = Math.max(ball.r, Math.min(W - ball.r, ball.x));
  pushTrail();

  score += dt * 12;
  const cfg = DIFF[difficulty];

  spawnTimer -= dt;
  if (spawnTimer <= 0) {
    const ok = spawnObstacle();
    spawnTimer = ok
      ? Math.max(0.28, cfg.spawn - score * 0.0012)
      : 0.15;
  }

  const baseSpeed = cfg.speed + Math.min(360, score * 0.5);

  for (let i = obstacles.length - 1; i >= 0; i--) {
    const o = obstacles[i];
    o.speed = baseSpeed * o.speedMul;
    o.y += o.speed * dt;

    if (o.type === 'mine') {
      o.x += o.vx * dt;
      if (o.x < 8) { o.x = 8; o.vx *= -1; }
      if (o.x + o.w > W - 8) { o.x = W - 8 - o.w; o.vx *= -1; }
      o.angle += o.spin * dt;
    }

    if (o.y > H + 160) { obstacles.splice(i, 1); continue; }

    if (o.type === 'mine') {
      const cx = o.x + o.w / 2, cy = o.y + o.h / 2;
      const rr = o.w / 2 - 2 + ball.r;
      const dx = ball.x - cx, dy = ball.y - cy;
      if (dx * dx + dy * dy < rr * rr) gameOver();
    } else {
      const pad = (o.type === 'log') ? 6 : (o.type === 'iceberg' ? 14 : 5);
      const rx = o.x + pad, ry = o.y + pad;
      const rw = o.w - pad * 2, rh = o.h - pad * 2;
      const nx = Math.max(rx, Math.min(ball.x, rx + rw));
      const ny = Math.max(ry, Math.min(ball.y, ry + rh));
      const dx = ball.x - nx, dy = ball.y - ny;
      if (dx * dx + dy * dy < ball.r * ball.r) gameOver();
    }
  }
}

function pushTrail() {
  ball.trail.push({ x: ball.x, y: ball.y });
  if (ball.trail.length > 14) ball.trail.shift();
}

function drawSea(t) {
  const g = ctx.createLinearGradient(0, 0, 0, H);
  g.addColorStop(0.00, '#0a2547');
  g.addColorStop(0.55, '#10406e');
  g.addColorStop(1.00, '#061625');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, W, H);

  const sun = ctx.createRadialGradient(W * 0.72, -60, 30, W * 0.72, -60, H * 1.05);
  sun.addColorStop(0, 'rgba(255, 222, 160, 0.14)');
  sun.addColorStop(1, 'rgba(255, 222, 160, 0)');
  ctx.fillStyle = sun;
  ctx.fillRect(0, 0, W, H);

  for (let layer = 0; layer < 3; layer++) {
    const baseY = H * 0.25 + layer * (H * 0.30);
    const amp = 8 + layer * 3;
    const spd = 0.45 + layer * 0.28;
    const alpha = 0.05 + layer * 0.03;

    ctx.beginPath();
    ctx.moveTo(0, H);
    for (let x = 0; x <= W; x += 8) {
      const y = baseY
        + Math.sin(x * 0.0075 + t * spd + layer * 1.3) * amp
        + Math.sin(x * 0.0205 - t * spd * 1.6 + layer * 2.4) * (amp * 0.4);
      ctx.lineTo(x, y);
    }
    ctx.lineTo(W, H);
    ctx.closePath();

    const wg = ctx.createLinearGradient(0, baseY - amp * 2, 0, H);
    wg.addColorStop(0, `rgba(130, 205, 255, ${alpha})`);
    wg.addColorStop(1, `rgba(6, 30, 60, ${alpha * 0.5})`);
    ctx.fillStyle = wg;
    ctx.fill();

    ctx.beginPath();
    for (let x = 0; x <= W; x += 8) {
      const y = baseY
        + Math.sin(x * 0.0075 + t * spd + layer * 1.3) * amp
        + Math.sin(x * 0.0205 - t * spd * 1.6 + layer * 2.4) * (amp * 0.4);
      if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = `rgba(170, 225, 255, ${0.05 + layer * 0.015})`;
    ctx.lineWidth = 1.4;
    ctx.stroke();
  }

  const vg = ctx.createRadialGradient(W/2, H/2, Math.min(W,H)*0.35, W/2, H/2, Math.max(W,H)*0.75);
  vg.addColorStop(0, 'rgba(0,0,0,0)');
  vg.addColorStop(1, 'rgba(0,0,0,0.5)');
  ctx.fillStyle = vg;
  ctx.fillRect(0, 0, W, H);
}

function drawTrail() {
  const tr = save.equipped.trail;
  for (let i = 0; i < ball.trail.length; i++) {
    const p = ball.trail[i];
    const k = i / ball.trail.length;
    let color;
    if (tr === 'trail_rainbow') {
      const hue = (performance.now() / 8 + i * 22) % 360;
      color = `hsla(${hue}, 90%, 65%, ${k * 0.5})`;
    } else if (tr === 'trail_ice') {
      color = `rgba(150, 230, 255, ${k * 0.55})`;
    } else {
      color = `rgba(140, 200, 255, ${k * 0.28})`;
    }
    ctx.beginPath();
    ctx.arc(p.x, p.y, ball.r * (0.3 + k * 0.65), 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
  }
}

function drawPirateHat(x, y, r) {
  const w = r * 2.4;
  const baseY = y - r * 0.55;

  ctx.fillStyle = '#111';
  ctx.beginPath();
  ctx.ellipse(x, baseY, w / 2, r * 0.32, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.beginPath();
  ctx.moveTo(x - w * 0.32, baseY);
  ctx.quadraticCurveTo(x - w * 0.30, baseY - r * 1.05, x, baseY - r * 1.10);
  ctx.quadraticCurveTo(x + w * 0.30, baseY - r * 1.05, x + w * 0.32, baseY);
  ctx.closePath();
  ctx.fill();

  ctx.fillStyle = '#e8e8e8';
  ctx.beginPath();
  ctx.arc(x, baseY - r * 0.55, r * 0.28, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = '#111';
  ctx.beginPath(); ctx.arc(x - r * 0.10, baseY - r * 0.57, r * 0.07, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.arc(x + r * 0.10, baseY - r * 0.57, r * 0.07, 0, Math.PI * 2); ctx.fill();
}

function drawBall() {
  const { x, y, r } = ball;
  drawTrail();

  const bg = ctx.createRadialGradient(
    x - r * 0.38, y - r * 0.45, r * 0.10,
    x, y, r * 1.05
  );
  bg.addColorStop(0.00, '#ffffff');
  bg.addColorStop(0.35, '#d6efff');
  bg.addColorStop(0.68, '#7dc0f5');
  bg.addColorStop(1.00, '#2a63ad');
  ctx.fillStyle = bg;
  ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();

  ctx.fillStyle = 'rgba(255,255,255,0.9)';
  ctx.beginPath();
  ctx.ellipse(x - r * 0.32, y - r * 0.42, r * 0.28, r * 0.16, -0.55, 0, Math.PI * 2);
  ctx.fill();

  ctx.strokeStyle = 'rgba(205, 240, 255, 0.9)';
  ctx.lineWidth = 1.6;
  ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.stroke();

  if (save.equipped.hat === 'hat_pirate') {
    drawPirateHat(x, y, r);
  }
}

function drawObstacle(o) {
  const cx = o.x + o.w / 2;
  const cy = o.y + o.h / 2;

  if (o.type === 'rock' || o.type === 'iceberg') {
    ctx.save();
    ctx.translate(cx, cy);

    ctx.beginPath();
    ctx.ellipse(0, o.h * 0.55, o.w * 0.5, o.h * 0.13, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(0,0,0,0.22)';
    ctx.fill();

    ctx.beginPath();
    o.shape.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.closePath();

    const g = ctx.createLinearGradient(0, -o.h/2, 0, o.h/2);
    if (o.type === 'rock') {
      g.addColorStop(0, '#6d6d72');
      g.addColorStop(0.5, '#46464c');
      g.addColorStop(1, '#26262b');
    } else {
      g.addColorStop(0, '#ffffff');
      g.addColorStop(0.5, '#d5f0ff');
      g.addColorStop(1, '#79bfe8');
    }
    ctx.fillStyle = g;
    ctx.fill();
    ctx.strokeStyle = (o.type === 'rock') ? 'rgba(15,15,20,0.85)' : 'rgba(150,215,245,0.9)';
    ctx.lineWidth = 1.4;
    ctx.stroke();
    ctx.restore();

  } else if (o.type === 'log') {
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(o.angle);

    const w = o.w, h = o.h, r = h / 2;

    ctx.beginPath();
    ctx.ellipse(0, h * 0.9, w * 0.42, h * 0.28, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(0,0,0,0.22)';
    ctx.fill();

    const g = ctx.createLinearGradient(0, -r, 0, r);
    g.addColorStop(0, '#a8712f');
    g.addColorStop(0.5, '#7d4f1e');
    g.addColorStop(1, '#4a2c0e');
    ctx.fillStyle = g;
    roundRect(-w/2, -r, w, h, r);
    ctx.fill();
    ctx.strokeStyle = 'rgba(40, 22, 6, 0.9)';
    ctx.lineWidth = 1.3;
    ctx.stroke();

    ctx.beginPath(); ctx.arc(-w/2 + r, 0, r - 1, 0, Math.PI * 2);
    ctx.fillStyle = '#c9975a'; ctx.fill();
    ctx.strokeStyle = 'rgba(70, 42, 14, 0.8)'; ctx.stroke();
    ctx.restore();

  } else {
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(o.angle);
    const R = o.w / 2;

    ctx.beginPath();
    ctx.ellipse(0, R * 0.95, R * 0.85, R * 0.25, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(0,0,0,0.25)';
    ctx.fill();

    ctx.strokeStyle = '#1b1f26';
    ctx.lineWidth = 4;
    ctx.lineCap = 'round';
    for (let i = 0; i < 8; i++) {
      const a = (i / 8) * Math.PI * 2;
      ctx.beginPath();
      ctx.moveTo(Math.cos(a) * R * 0.75, Math.sin(a) * R * 0.75);
      ctx.lineTo(Math.cos(a) * R * 1.25, Math.sin(a) * R * 1.25);
      ctx.stroke();
    }
    ctx.lineCap = 'butt';

    const g = ctx.createRadialGradient(-R * 0.35, -R * 0.4, R * 0.1, 0, 0, R);
    g.addColorStop(0, '#5c646f');
    g.addColorStop(0.55, '#2c333c');
    g.addColorStop(1, '#12161b');
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.arc(0, 0, R, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = '#0a0d11';
    ctx.lineWidth = 1.4;
    ctx.stroke();

    const blink = 0.5 + 0.5 * Math.sin(performance.now() / 180);
    ctx.beginPath(); ctx.arc(0, -R * 0.6, 2.6, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(255, 70, 70, ${0.4 + blink * 0.6})`;
    ctx.fill();
    ctx.restore();
  }
}

function drawButton(x, y, w, h, text, opts, onClick) {
  opts = opts || {};
  const { active = false, primary = false, disabled = false, font = 'bold 20px Georgia, serif' } = opts;

  const g = ctx.createLinearGradient(0, y, 0, y + h);
  if (disabled) {
    g.addColorStop(0, 'rgba(255,255,255,0.06)');
    g.addColorStop(1, 'rgba(255,255,255,0.03)');
  } else if (active) {
    g.addColorStop(0, '#56b6ff'); g.addColorStop(1, '#1c62b8');
  } else if (primary) {
    g.addColorStop(0, '#5fd98d'); g.addColorStop(1, '#238a52');
  } else {
    g.addColorStop(0, 'rgba(255,255,255,0.13)');
    g.addColorStop(1, 'rgba(255,255,255,0.045)');
  }

  ctx.fillStyle = g;
  roundRect(x, y, w, h, 10);
  ctx.fill();

  ctx.strokeStyle = disabled ? 'rgba(255,255,255,0.12)'
                  : active ? '#9ad4ff'
                  : primary ? '#9df3bf'
                  : 'rgba(255,255,255,0.22)';
  ctx.lineWidth = 1.6;
  roundRect(x, y, w, h, 10);
  ctx.stroke();

  ctx.fillStyle = disabled ? 'rgba(255,255,255,0.35)' : '#ffffff';
  ctx.font = font;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, x + w / 2, y + h / 2 + 1);
  ctx.textBaseline = 'alphabetic';

  if (!disabled) hitAreas.push({ x, y, w, h, onClick });
}

function drawMenu() {
  ctx.fillStyle = 'rgba(4, 12, 26, 0.55)';
  ctx.fillRect(0, 0, W, H);
  ctx.textAlign = 'center';

  ctx.fillStyle = '#eef7ff';
  ctx.font = 'bold 58px Georgia, serif';
  ctx.fillText('BALL AT SEA', W / 2, H / 2 - 165);

  ctx.font = '16px Georgia, serif';
  ctx.fillStyle = 'rgba(190, 220, 250, 0.72)';
  ctx.fillText('Move the mouse — dodge obstacles', W / 2, H / 2 - 132);

  const keys = ['easy', 'normal', 'hard'];
  const bw = 130, bh = 46, gap = 14;
  const total = keys.length * bw + (keys.length - 1) * gap;
  let bx = W / 2 - total / 2;
  const by = H / 2 - 90;
  for (const k of keys) {
    const kk = k;
    drawButton(bx, by, bw, bh, DIFF[kk].label, { active: difficulty === kk, font: 'bold 17px Georgia, serif' },
      () => { difficulty = kk; save.difficulty = kk; persistSave(); });
    bx += bw + gap;
  }

  const pw = 240, ph = 58;
  drawButton(W / 2 - pw / 2, H / 2 - 10, pw, ph, 'PLAY',
    { primary: true, font: 'bold 22px Georgia, serif' }, startGame);

  const sw = 240, sh = 50;
  drawButton(W / 2 - sw / 2, H / 2 + 66, sw, sh, 'SHOP',
    { font: 'bold 18px Georgia, serif' }, () => { state = 'shop'; });

  ctx.font = '15px Georgia, serif';
  ctx.fillStyle = 'rgba(180, 215, 245, 0.65)';
  ctx.fillText('Total points: ' + Math.floor(save.totalPoints), W / 2, H / 2 + 156);
  ctx.fillText('Best run: ' + Math.floor(save.best) + '   |   Runs: ' + save.runs, W / 2, H / 2 + 180);
}

function drawShopPreview(cx, cy, item) {
  const R = 12;

  if (item.id === 'trail_ice') {
    for (let i = 4; i >= 0; i--) {
      const a = i / 4;
      ctx.beginPath();
      ctx.arc(cx - 22 + i * 6, cy + 6, R * (0.3 + a * 0.6), 0, Math.PI * 2);
      ctx.fillStyle = `rgba(150, 230, 255, ${a * 0.75})`;
      ctx.fill();
    }
    const g = ctx.createRadialGradient(cx - R*0.4, cy - R*0.5, 1, cx, cy, R);
    g.addColorStop(0, '#ffffff'); g.addColorStop(0.5, '#d6efff'); g.addColorStop(1, '#2a63ad');
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.fillStyle = g; ctx.fill();
    ctx.strokeStyle = 'rgba(205, 240, 255, 0.9)'; ctx.lineWidth = 1.2; ctx.stroke();

  } else if (item.id === 'hat_pirate') {
    const r = 14;
    drawPirateHat(cx, cy + r * 0.35, r);

  } else {
    for (let i = 4; i >= 0; i--) {
      const a = i / 4;
      const hue = (i * 60) % 360;
      ctx.beginPath();
      ctx.arc(cx - 22 + i * 6, cy + 6, R * (0.3 + a * 0.6), 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${hue}, 90%, 65%, ${a * 0.8})`;
      ctx.fill();
    }
    const g = ctx.createRadialGradient(cx - R*0.4, cy - R*0.5, 1, cx, cy, R);
    g.addColorStop(0, '#ffffff'); g.addColorStop(0.5, '#d6efff'); g.addColorStop(1, '#2a63ad');
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.fillStyle = g; ctx.fill();
    ctx.strokeStyle = 'rgba(205, 240, 255, 0.9)'; ctx.lineWidth = 1.2; ctx.stroke();
  }
}

function drawShopItem(x, y, w, h, item) {
  const owned = save.owned[item.id];
  const equipped = save.equipped[item.type] === item.id;
  const canBuy = save.totalPoints >= item.price;

  ctx.fillStyle = equipped ? 'rgba(60, 140, 90, 0.18)' : 'rgba(255,255,255,0.06)';
  roundRect(x, y, w, h, 10);
  ctx.fill();
  ctx.strokeStyle = equipped ? '#7fe0a0' : 'rgba(255,255,255,0.15)';
  ctx.lineWidth = 1.4;
  roundRect(x, y, w, h, 10);
  ctx.stroke();

  const pv = 64;
  const px = x + 16;
  const py = y + (h - pv) / 2;
  ctx.fillStyle = 'rgba(0,0,0,0.3)';
  roundRect(px, py, pv, pv, 8);
  ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.1)';
  ctx.lineWidth = 1;
  roundRect(px, py, pv, pv, 8);
  ctx.stroke();

  ctx.save();
  ctx.beginPath();
  roundRect(px, py, pv, pv, 8);
  ctx.clip();
  drawShopPreview(px + pv / 2, py + pv / 2, item);
  ctx.restore();

  const textX = px + pv + 18;

  ctx.textAlign = 'left';
  ctx.fillStyle = '#eef7ff';
  ctx.font = 'bold 19px Georgia, serif';
  ctx.fillText(item.name, textX, y + 32);

  ctx.font = '13px Georgia, serif';
  ctx.fillStyle = 'rgba(180, 210, 240, 0.7)';
  ctx.fillText(item.desc, textX, y + 54);

  let badge = null;
  if (equipped) badge = { text: 'EQUIPPED', color: '#7fe0a0' };
  else if (owned) badge = { text: 'OWNED', color: '#9ad4ff' };
  if (badge) {
    ctx.font = 'bold 11px Georgia, serif';
    const tw = ctx.measureText(badge.text).width + 14;
    ctx.fillStyle = 'rgba(0,0,0,0.35)';
    roundRect(textX, y + 62, tw, 18, 6);
    ctx.fill();
    ctx.fillStyle = badge.color;
    ctx.textAlign = 'center';
    ctx.fillText(badge.text, textX + tw / 2, y + 75);
    ctx.textAlign = 'left';
  }

  const btnW = 140, btnH = 40;
  const btnX = x + w - btnW - 14;
  const btnY = y + (h - btnH) / 2;

  let label, active = false, primary = false, disabled = false, onClick;
  if (equipped) {
    label = 'UNEQUIP'; active = true;
    onClick = () => { save.equipped[item.type] = (item.type === 'trail') ? 'default' : null; persistSave(); };
  } else if (owned) {
    label = 'EQUIP'; primary = true;
    onClick = () => { save.equipped[item.type] = item.id; persistSave(); };
  } else if (canBuy) {
    label = 'BUY ' + item.price; primary = true;
    onClick = () => {
      save.totalPoints -= item.price;
      save.owned[item.id] = true;
      save.equipped[item.type] = item.id;
      persistSave();
    };
  } else {
    label = item.price + ' PTS'; disabled = true;
    onClick = () => {};
  }

  drawButton(btnX, btnY, btnW, btnH, label,
    { active, primary, disabled, font: 'bold 15px Georgia, serif' }, onClick);
}

function drawShop() {
  ctx.fillStyle = 'rgba(4, 12, 26, 0.9)';
  ctx.fillRect(0, 0, W, H);

  ctx.textAlign = 'center';
  ctx.fillStyle = '#eef7ff';
  ctx.font = 'bold 42px Georgia, serif';
  ctx.fillText('SHOP', W / 2, 80);

  ctx.font = '16px Georgia, serif';
  ctx.fillStyle = 'rgba(190, 220, 250, 0.85)';
  ctx.fillText('Balance: ' + Math.floor(save.totalPoints) + ' PTS', W / 2, 112);

  ctx.font = '13px Georgia, serif';
  ctx.fillStyle = 'rgba(160, 195, 230, 0.55)';
  ctx.fillText('Earn points by playing. Progress is saved automatically.', W / 2, 136);

  const itemW = Math.min(620, W - 60);
  const itemH = 96, gap = 12;
  const startY = 162;
  for (let i = 0; i < SHOP_ITEMS.length; i++) {
    const y = startY + i * (itemH + gap);
    drawShopItem(W / 2 - itemW / 2, y, itemW, itemH, SHOP_ITEMS[i]);
  }

  const bw = 200, bh = 50;
  drawButton(W / 2 - bw / 2, H - 92, bw, bh, 'BACK',
    { font: 'bold 18px Georgia, serif' }, () => { state = 'menu'; });
}

function drawHUD() {
  ctx.textAlign = 'left';
  ctx.font = 'bold 20px Georgia, serif';
  ctx.fillStyle = 'rgba(230, 245, 255, 0.92)';
  ctx.fillText('Score: ' + Math.floor(score), 22, 36);

  ctx.font = '14px Georgia, serif';
  ctx.fillStyle = 'rgba(170, 210, 245, 0.65)';
  ctx.fillText('Best: ' + Math.floor(save.best), 22, 58);

  ctx.textAlign = 'right';
  ctx.fillStyle = 'rgba(170, 210, 245, 0.55)';
  ctx.fillText(DIFF[difficulty].label, W - 22, 36);
}

function drawOver() {
  ctx.fillStyle = 'rgba(2, 8, 18, 0.7)';
  ctx.fillRect(0, 0, W, H);
  ctx.textAlign = 'center';

  ctx.fillStyle = '#ffeaea';
  ctx.font = 'bold 50px Georgia, serif';
  ctx.fillText('GAME OVER', W / 2, H / 2 - 40);

  if (newRecord) {
    const pulse = 0.6 + 0.4 * Math.sin(performance.now() / 300);
    ctx.fillStyle = `rgba(255, 220, 100, ${0.5 + pulse * 0.5})`;
    ctx.font = 'bold 18px Georgia, serif';
    ctx.fillText('NEW RECORD', W / 2, H / 2 - 5);
  }

  ctx.font = '22px Georgia, serif';
  ctx.fillStyle = '#dceaf7';
  ctx.fillText('Score: ' + Math.floor(score), W / 2, H / 2 + 26);

  ctx.font = '16px Georgia, serif';
  ctx.fillStyle = 'rgba(190, 220, 245, 0.7)';
  ctx.fillText('Best: ' + Math.floor(save.best), W / 2, H / 2 + 56);
  ctx.fillText('+ ' + Math.floor(score) + ' points added', W / 2, H / 2 + 82);

  if (overTimer > 0.4) {
    const pulse = 0.6 + 0.4 * Math.sin(performance.now() / 320);
    ctx.fillStyle = `rgba(255,255,255,${0.55 + pulse * 0.4})`;
    ctx.font = '18px Georgia, serif';
    ctx.fillText('Click or press SPACE to retry', W / 2, H / 2 + 130);
    ctx.fillStyle = 'rgba(190, 220, 245, 0.6)';
    ctx.font = '14px Georgia, serif';
    ctx.fillText('ESC — back to menu', W / 2, H / 2 + 158);
  }
}

function loop(now) {
  const dt = Math.min(0.05, (now - lastTime) / 1000) || 0;
  lastTime = now;
  const t = now / 1000;

  hitAreas = [];
  update(dt);

  ctx.save();
  if (shakeT > 0) {
    const s = shakeT * 22;
    ctx.translate(rand(-s, s), rand(-s, s));
  }

  drawSea(t);
  if (state === 'play' || state === 'over') {
    for (const o of obstacles) drawObstacle(o);
  }
  drawBall();
  ctx.restore();

  if (state === 'menu')      drawMenu();
  else if (state === 'shop') drawShop();
  else if (state === 'play') drawHUD();
  else if (state === 'over') { drawHUD(); drawOver(); }

  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);

canvas.addEventListener('mousemove', e => { mouseX = e.clientX; });

canvas.addEventListener('click', e => {
  for (const a of hitAreas) {
    if (e.clientX >= a.x && e.clientX <= a.x + a.w &&
        e.clientY >= a.y && e.clientY <= a.y + a.h) {
      a.onClick();
      return;
    }
  }
  if (state === 'over' && overTimer > 0.4) startGame();
});

window.addEventListener('keydown', e => {
  if (e.code === 'Space' && state === 'over' && overTimer > 0.4) {
    e.preventDefault();
    startGame();
  }
  if (e.code === 'Escape') {
    if (state === 'play') {
      commitRun();
      state = 'menu';
      obstacles = [];
      ball.trail = [];
    } else if (state === 'over') {
      state = 'menu';
      obstacles = [];
      ball.trail = [];
    } else if (state === 'shop') {
      state = 'menu';
    }
  }
});
</script>
</body>
</html>
"""


if __name__ == '__main__':
    api = SaveApi()
    webview.create_window('Ball at Sea', html=HTML, js_api=api, width=960, height=720)
    webview.start()