const canvas = document.querySelector("#tunnel");
const ctx = canvas.getContext("2d");
const startButton = document.querySelector("#startButton");
const muteButton = document.querySelector("#muteButton");
const tempoInput = document.querySelector("#tempo");
const tempoValue = document.querySelector("#tempoValue");
const scoreEl = document.querySelector("#score");
const comboEl = document.querySelector("#combo");
const accuracyEl = document.querySelector("#accuracy");
const laneButtons = [...document.querySelectorAll(".lane-key")];

const lanes = [
  { key: "d", color: "#ff4f8b", tone: 92 },
  { key: "f", color: "#55d6ff", tone: 294 },
  { key: "j", color: "#b7ff5d", tone: 220 },
  { key: "k", color: "#ffd166", tone: 466 }
];

let width = 0;
let height = 0;
let centerX = 0;
let centerY = 0;
let running = false;
let muted = false;
let bpm = Number(tempoInput.value);
let score = 0;
let combo = 0;
let hits = 0;
let attempts = 0;
let nextBeat = 0;
let lastFrame = 0;
let tunnelSpin = 0;
let audioContext;
let masterGain;

const notes = [];
const sparks = [];
const stars = Array.from({ length: 130 }, () => ({
  angle: Math.random() * Math.PI * 2,
  depth: Math.random(),
  speed: 0.18 + Math.random() * 0.7,
  size: 0.4 + Math.random() * 1.8
}));

function resize() {
  const scale = window.devicePixelRatio || 1;
  width = window.innerWidth;
  height = window.innerHeight;
  centerX = width / 2;
  centerY = height / 2;
  canvas.width = Math.floor(width * scale);
  canvas.height = Math.floor(height * scale);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
}

function ensureAudio() {
  if (audioContext) return;
  audioContext = new (window.AudioContext || window.webkitAudioContext)();
  masterGain = audioContext.createGain();
  masterGain.gain.value = muted ? 0 : 0.18;
  masterGain.connect(audioContext.destination);
}

function playTone(frequency, duration = 0.08, type = "triangle") {
  if (!audioContext || muted) return;
  const now = audioContext.currentTime;
  const osc = audioContext.createOscillator();
  const gain = audioContext.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(frequency, now);
  gain.gain.setValueAtTime(0.0001, now);
  gain.gain.exponentialRampToValueAtTime(0.58, now + 0.01);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);
  osc.connect(gain).connect(masterGain);
  osc.start(now);
  osc.stop(now + duration + 0.02);
}

function beatInterval() {
  return 60000 / bpm;
}

function spawnNote(time) {
  const laneIndex = Math.floor(Math.random() * lanes.length);
  const doubleChance = combo > 12 ? 0.28 : 0.14;
  notes.push({ laneIndex, born: time, depth: 1, hit: false, missed: false });

  if (Math.random() < doubleChance) {
    let secondLane = Math.floor(Math.random() * lanes.length);
    if (secondLane === laneIndex) secondLane = (secondLane + 1) % lanes.length;
    notes.push({ laneIndex: secondLane, born: time, depth: 1, hit: false, missed: false });
  }
}

function start() {
  ensureAudio();
  audioContext.resume();
  running = true;
  score = 0;
  combo = 0;
  hits = 0;
  attempts = 0;
  notes.length = 0;
  sparks.length = 0;
  nextBeat = performance.now() + 300;
  startButton.classList.add("is-running");
  updateHud();
}

function laneAngle(index) {
  const base = -Math.PI / 2;
  return base + (index / lanes.length) * Math.PI * 2 + tunnelSpin * 0.22;
}

function targetRadius() {
  return Math.min(width, height) * 0.17;
}

function noteRadius(depth) {
  const maxR = Math.hypot(width, height) * 0.68;
  const minR = targetRadius();
  return minR + (maxR - minR) * depth * depth;
}

function hitLane(key) {
  const laneIndex = lanes.findIndex((lane) => lane.key === key.toLowerCase());
  if (laneIndex < 0) return;
  ensureAudio();
  attempts += 1;
  const button = laneButtons[laneIndex];
  button.classList.add("is-active");
  setTimeout(() => button.classList.remove("is-active"), 95);

  const candidates = notes
    .filter((note) => note.laneIndex === laneIndex && !note.hit && !note.missed)
    .map((note) => ({ note, distance: Math.abs(note.depth - 0.02) }))
    .sort((a, b) => a.distance - b.distance);

  if (candidates[0] && candidates[0].distance < 0.105) {
    const note = candidates[0].note;
    const precision = Math.max(0, 1 - candidates[0].distance / 0.105);
    note.hit = true;
    combo += 1;
    hits += 1;
    score += Math.round(180 + precision * 820 + combo * 7);
    burst(laneIndex, precision);
    playTone(lanes[laneIndex].tone * (precision > 0.8 && laneIndex !== 0 ? 2 : 1), laneIndex === 0 ? 0.045 : 0.09);
  } else {
    combo = 0;
    playTone(82, 0.05, "sawtooth");
  }

  updateHud();
}

function burst(laneIndex, power) {
  const angle = laneAngle(laneIndex);
  const radius = targetRadius();
  const x = centerX + Math.cos(angle) * radius;
  const y = centerY + Math.sin(angle) * radius;
  for (let i = 0; i < 18; i += 1) {
    sparks.push({
      x,
      y,
      vx: (Math.random() - 0.5) * (3 + power * 7),
      vy: (Math.random() - 0.5) * (3 + power * 7),
      life: 1,
      color: lanes[laneIndex].color
    });
  }
}

function updateHud() {
  scoreEl.textContent = String(score).padStart(6, "0");
  comboEl.textContent = String(combo);
  accuracyEl.textContent = `${attempts ? Math.round((hits / attempts) * 100) : 100}%`;
}

function drawTunnel(delta) {
  tunnelSpin += delta * 0.00024 * (running ? 1.8 : 0.8);
  ctx.clearRect(0, 0, width, height);

  const rings = 22;
  for (let i = 0; i < rings; i += 1) {
    const depth = ((i / rings + tunnelSpin * 0.18) % 1);
    const radius = 24 + depth * Math.hypot(width, height) * 0.68;
    const alpha = Math.pow(1 - depth, 1.7) * 0.55;
    ctx.strokeStyle = `rgba(85, 214, 255, ${alpha})`;
    ctx.lineWidth = 1 + (1 - depth) * 4;
    ctx.beginPath();
    polygon(centerX, centerY, radius, 14, tunnelSpin + depth * 2.4);
    ctx.stroke();
  }

  for (let i = 0; i < lanes.length; i += 1) {
    const angle = laneAngle(i);
    const endR = Math.hypot(width, height) * 0.72;
    const startR = targetRadius() * 0.55;
    const gradient = ctx.createLinearGradient(
      centerX + Math.cos(angle) * startR,
      centerY + Math.sin(angle) * startR,
      centerX + Math.cos(angle) * endR,
      centerY + Math.sin(angle) * endR
    );
    gradient.addColorStop(0, `${lanes[i].color}cc`);
    gradient.addColorStop(1, `${lanes[i].color}00`);
    ctx.strokeStyle = gradient;
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(centerX + Math.cos(angle) * startR, centerY + Math.sin(angle) * startR);
    ctx.lineTo(centerX + Math.cos(angle) * endR, centerY + Math.sin(angle) * endR);
    ctx.stroke();
  }

  stars.forEach((star) => {
    star.depth -= delta * 0.00008 * star.speed * (running ? 1.8 : 0.7);
    if (star.depth < 0) {
      star.depth = 1;
      star.angle = Math.random() * Math.PI * 2;
    }
    const radius = noteRadius(star.depth);
    ctx.fillStyle = `rgba(247, 251, 255, ${0.7 * (1 - star.depth)})`;
    ctx.beginPath();
    ctx.arc(centerX + Math.cos(star.angle) * radius, centerY + Math.sin(star.angle) * radius, star.size, 0, Math.PI * 2);
    ctx.fill();
  });
}

function polygon(x, y, radius, sides, rotation) {
  for (let i = 0; i <= sides; i += 1) {
    const angle = rotation + (i / sides) * Math.PI * 2;
    const px = x + Math.cos(angle) * radius;
    const py = y + Math.sin(angle) * radius;
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
}

function drawNotes(delta) {
  const travelMs = 1850;
  const now = performance.now();
  for (const note of notes) {
    if (note.hit || note.missed) continue;
    note.depth = 1 - (now - note.born) / travelMs;
    if (note.depth < -0.11) {
      note.missed = true;
      combo = 0;
      attempts += 1;
      updateHud();
      continue;
    }
    const angle = laneAngle(note.laneIndex);
    const radius = noteRadius(Math.max(note.depth, 0));
    const size = 12 + (1 - Math.max(note.depth, 0)) * 24;
    const x = centerX + Math.cos(angle) * radius;
    const y = centerY + Math.sin(angle) * radius;
    ctx.fillStyle = lanes[note.laneIndex].color;
    ctx.shadowColor = lanes[note.laneIndex].color;
    ctx.shadowBlur = 26;
    ctx.beginPath();
    ctx.arc(x, y, size, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
  }

  for (let i = sparks.length - 1; i >= 0; i -= 1) {
    const spark = sparks[i];
    spark.life -= delta * 0.0022;
    spark.x += spark.vx;
    spark.y += spark.vy;
    if (spark.life <= 0) {
      sparks.splice(i, 1);
      continue;
    }
    ctx.fillStyle = `${spark.color}${Math.round(spark.life * 255).toString(16).padStart(2, "0")}`;
    ctx.beginPath();
    ctx.arc(spark.x, spark.y, 2.2 + spark.life * 3, 0, Math.PI * 2);
    ctx.fill();
  }
}

function frame(time) {
  const delta = lastFrame ? time - lastFrame : 16;
  lastFrame = time;
  drawTunnel(delta);

  if (running) {
    while (time >= nextBeat) {
      spawnNote(nextBeat);
      playTone(110, 0.025, "sine");
      nextBeat += beatInterval() / 2;
    }
  }

  drawNotes(delta);
  requestAnimationFrame(frame);
}

startButton.addEventListener("click", start);

muteButton.addEventListener("click", () => {
  muted = !muted;
  muteButton.setAttribute("aria-label", muted ? "Unmute audio" : "Mute audio");
  muteButton.style.opacity = muted ? "0.52" : "1";
  if (masterGain) masterGain.gain.value = muted ? 0 : 0.18;
});

tempoInput.addEventListener("input", () => {
  bpm = Number(tempoInput.value);
  tempoValue.textContent = String(bpm);
});

laneButtons.forEach((button) => {
  button.addEventListener("pointerdown", () => hitLane(button.dataset.key));
});

window.addEventListener("keydown", (event) => {
  const key = event.key.toLowerCase();
  if (key === "escape") {
    window.location.href = "./";
    return;
  }
  if (key === " " && !running) {
    event.preventDefault();
    start();
    return;
  }
  if (lanes.some((lane) => lane.key === key)) {
    event.preventDefault();
    hitLane(key);
  }
});

window.addEventListener("resize", resize);

resize();
requestAnimationFrame(frame);
