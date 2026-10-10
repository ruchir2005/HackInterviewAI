/* ────────────────────────────────────────────────
   Voice Analysis Demo – app.js
   Real microphone capture + openSMILE-style features
   ──────────────────────────────────────────────── */

// ── Particle Background ──────────────────────────
(function initParticles() {
  const canvas = document.getElementById('particles');
  const ctx = canvas.getContext('2d');
  let w, h, dots = [];

  function resize() {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
  }
  window.addEventListener('resize', resize);
  resize();

  for (let i = 0; i < 80; i++) {
    dots.push({
      x: Math.random() * w,
      y: Math.random() * h,
      r: Math.random() * 1.8 + 0.4,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      alpha: Math.random() * 0.4 + 0.1,
    });
  }

  function draw() {
    ctx.clearRect(0, 0, w, h);
    dots.forEach(d => {
      d.x += d.vx;
      d.y += d.vy;
      if (d.x < 0) d.x = w;
      if (d.x > w) d.x = 0;
      if (d.y < 0) d.y = h;
      if (d.y > h) d.y = 0;
      ctx.beginPath();
      ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(0,212,255,${d.alpha})`;
      ctx.fill();
    });
    requestAnimationFrame(draw);
  }
  draw();
})();

// ── Feature Config ───────────────────────────────
const FEATURES = {
  pitchMean: { min: 0, max: 40, unit: 'semitones', decimals: 1 },
  pitchVar: { min: 0, max: 1, unit: '', decimals: 3 },
  loudMean: { min: 0, max: 1, unit: 'sone', decimals: 3 },
  loudVar: { min: 0, max: 0.5, unit: '', decimals: 3 },
  jitter: { min: 0.005, max: 0.06, unit: '%', decimals: 4 },
  shimmer: { min: 0.3, max: 2.5, unit: 'dB', decimals: 2 },
  speechRate: { min: 1, max: 6, unit: 'syl/s', decimals: 1 },
  pauseRatio: { min: 5, max: 50, unit: '%', decimals: 1 },
};

// ── DOM Helpers ──────────────────────────────────
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

function getCard(metric) {
  return document.querySelector(`.meter-card[data-metric="${metric}"]`);
}

function setMeter(metric, value) {
  const card = getCard(metric);
  if (!card) return;
  const cfg = FEATURES[metric];
  const pct = ((value - cfg.min) / (cfg.max - cfg.min)) * 100;
  card.querySelector('.meter-bar').style.width = clamp(pct, 0, 100) + '%';
  const display = metric === 'jitter'
    ? (value * 100).toFixed(2)
    : value.toFixed(cfg.decimals);
  card.querySelector('.meter-value').innerHTML =
    `${display} <small>${cfg.unit}</small>`;
}

function setRing(scoreId, value) {
  const card = document.querySelector(`.score-ring-card[data-score="${scoreId}"]`);
  if (!card) return;
  const circumference = 2 * Math.PI * 52;
  const offset = circumference - (value / 5) * circumference;
  card.querySelector('.ring-fill').style.strokeDashoffset = offset;
  card.querySelector('.ring-label').textContent = value.toFixed(1);
}

function resetAll() {
  Object.keys(FEATURES).forEach(m => {
    const card = getCard(m);
    card.querySelector('.meter-bar').style.width = '0%';
    card.querySelector('.meter-value').innerHTML = `— <small>${FEATURES[m].unit}</small>`;
  });
  ['tone', 'confidence', 'pace'].forEach(s => {
    const card = document.querySelector(`.score-ring-card[data-score="${s}"]`);
    card.querySelector('.ring-fill').style.strokeDashoffset = 326.73;
    card.querySelector('.ring-label').textContent = '—';
  });
}

// ── Scoring Formulas ─────────────────────────────
function toneScore(pitchVar) {
  return clamp(5 * (1 - Math.abs(pitchVar - 0.5) * 2), 0, 5);
}

function confidenceScore(jitter, shimmer) {
  return clamp(5 - (jitter * 50) - (shimmer * 2), 0, 5);
}

function paceScore(speechRate, pauseRatio) {
  let rateSub;
  if (speechRate >= 3 && speechRate <= 4) rateSub = 5;
  else if (speechRate >= 2 && speechRate <= 5) rateSub = 3 + 2 * (1 - Math.abs(speechRate - 3.5) / 1.5);
  else rateSub = Math.max(0, 5 - Math.abs(speechRate - 3.5) * 2);

  const pauseSub = clamp(5 - Math.abs(pauseRatio - 20) * 0.25, 0, 5);
  return clamp((rateSub + pauseSub) / 2, 0, 5);
}

// ── Simulated Demo ───────────────────────────────
function generateSample() {
  const r = (a, b) => a + Math.random() * (b - a);
  return {
    pitchMean: r(16, 28), pitchVar: r(0.18, 0.32),
    loudMean: r(0.35, 0.65), loudVar: r(0.08, 0.18),
    jitter: r(0.012, 0.028), shimmer: r(0.5, 1.1),
    speechRate: r(2.8, 4.2), pauseRatio: r(16, 26),
  };
}

function runDemo() {
  const sample = generateSample();
  const keys = Object.keys(sample);
  keys.forEach((k, i) => setTimeout(() => setMeter(k, sample[k]), i * 120));
  setTimeout(() => {
    setRing('tone', toneScore(sample.pitchVar));
    setRing('confidence', confidenceScore(sample.jitter, sample.shimmer));
    setRing('pace', paceScore(sample.speechRate, sample.pauseRatio));
  }, keys.length * 120 + 300);
}

// ═══════════════════════════════════════════════════
//  REAL MICROPHONE VOICE ANALYSIS
// ═══════════════════════════════════════════════════

let audioCtx = null;
let analyser = null;
let micStream = null;
let isRecording = false;
let animFrameId = null;
let recordingStart = 0;
let timerInterval = null;

// Collection buffers
let pitchHistory = [];  // F0 in Hz per frame
let amplitudeHistory = []; // RMS per frame
let loudnessHistory = [];  // normalised loudness per frame
let frameCount = 0;
let silentFrames = 0;
let totalFrames = 0;
let syllableCount = 0;
let lastWasSyllable = false;
const SILENCE_THRESHOLD = 0.015;
const SYLLABLE_ENERGY_THRESHOLD = 0.04;

// ── Autocorrelation Pitch Detection ─────────────
function detectPitch(buffer, sampleRate) {
  // YIN-lite: autocorrelation method
  const SIZE = buffer.length;
  const MAX_SAMPLES = Math.floor(SIZE / 2);
  let bestOffset = -1;
  let bestCorrelation = 0;
  let foundGoodCorrelation = false;

  // Min/max pitch: 60 Hz – 500 Hz
  const minPeriod = Math.floor(sampleRate / 500);
  const maxPeriod = Math.floor(sampleRate / 60);

  const correlations = new Float32Array(MAX_SAMPLES);

  for (let offset = minPeriod; offset < maxPeriod && offset < MAX_SAMPLES; offset++) {
    let correlation = 0;
    let totalEnergy = 0;
    let shiftedEnergy = 0;
    for (let i = 0; i < MAX_SAMPLES; i++) {
      correlation += buffer[i] * buffer[i + offset];
      totalEnergy += buffer[i] * buffer[i];
      shiftedEnergy += buffer[i + offset] * buffer[i + offset];
    }
    // Normalized cross-correlation
    const norm = Math.sqrt(totalEnergy * shiftedEnergy);
    correlation = norm > 0 ? correlation / norm : 0;
    correlations[offset] = correlation;

    if (correlation > 0.9) {
      if (correlation > bestCorrelation) {
        bestCorrelation = correlation;
        bestOffset = offset;
      }
      foundGoodCorrelation = true;
    } else if (foundGoodCorrelation) {
      break;
    }
  }

  if (!foundGoodCorrelation) {
    // Lower threshold
    for (let offset = minPeriod; offset < maxPeriod && offset < MAX_SAMPLES; offset++) {
      if (correlations[offset] > 0.7 && correlations[offset] > bestCorrelation) {
        bestCorrelation = correlations[offset];
        bestOffset = offset;
      }
    }
  }

  if (bestCorrelation > 0.7 && bestOffset > 0) {
    return sampleRate / bestOffset;
  }
  return -1; // unvoiced
}

// ── Hz → Semitones from 27.5 Hz ──────────────────
function hzToSemitones(hz) {
  if (hz <= 0) return 0;
  return 12 * Math.log2(hz / 27.5);
}

// ── RMS Energy ───────────────────────────────────
function computeRMS(buffer) {
  let sum = 0;
  for (let i = 0; i < buffer.length; i++) {
    sum += buffer[i] * buffer[i];
  }
  return Math.sqrt(sum / buffer.length);
}

// ── Start Recording ──────────────────────────────
async function startRecording() {
  try {
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
    });
  } catch (err) {
    alert('Microphone access denied. Please allow microphone permission and try again.');
    return;
  }

  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const source = audioCtx.createMediaStreamSource(micStream);

  analyser = audioCtx.createAnalyser();
  analyser.fftSize = 4096;
  source.connect(analyser);

  // Reset buffers
  pitchHistory = [];
  amplitudeHistory = [];
  loudnessHistory = [];
  frameCount = 0;
  silentFrames = 0;
  totalFrames = 0;
  syllableCount = 0;
  lastWasSyllable = false;

  isRecording = true;
  recordingStart = Date.now();

  // UI
  const btn = document.getElementById('btn-record');
  btn.textContent = '⏹ Stop Recording';
  btn.classList.add('recording');
  document.getElementById('recording-status').classList.remove('hidden');
  resetAll();

  // Timer
  timerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - recordingStart) / 1000);
    const m = Math.floor(elapsed / 60);
    const s = elapsed % 60;
    document.getElementById('rec-timer').textContent = `${m}:${s.toString().padStart(2, '0')}`;
  }, 500);

  // Start analysis loop
  analyseFrame();
}

// ── Per-frame Analysis ───────────────────────────
function analyseFrame() {
  if (!isRecording) return;

  const bufLen = analyser.fftSize;
  const buffer = new Float32Array(bufLen);
  analyser.getFloatTimeDomainData(buffer);

  const rms = computeRMS(buffer);
  const sampleRate = audioCtx.sampleRate;

  totalFrames++;

  // Silence detection
  if (rms < SILENCE_THRESHOLD) {
    silentFrames++;
  } else {
    // Pitch detection (only on voiced frames)
    const f0 = detectPitch(buffer, sampleRate);
    if (f0 > 0) {
      pitchHistory.push(f0);
      amplitudeHistory.push(rms);
    }
    loudnessHistory.push(rms);

    // Syllable detection (energy peak)
    if (rms > SYLLABLE_ENERGY_THRESHOLD && !lastWasSyllable) {
      syllableCount++;
      lastWasSyllable = true;
    } else if (rms < SYLLABLE_ENERGY_THRESHOLD * 0.6) {
      lastWasSyllable = false;
    }
  }

  frameCount++;

  // Update meters in real-time every ~10 frames
  if (frameCount % 10 === 0 && pitchHistory.length > 2) {
    updateLiveMeters();
  }

  animFrameId = requestAnimationFrame(analyseFrame);
}

// ── Live Meter Updates ───────────────────────────
function updateLiveMeters() {
  const results = computeResults();
  if (!results) return;

  Object.keys(results).forEach(k => {
    if (FEATURES[k]) setMeter(k, results[k]);
  });
}

// ── Compute All Results ──────────────────────────
function computeResults() {
  if (pitchHistory.length < 3) return null;

  const elapsedSec = (Date.now() - recordingStart) / 1000;

  // Pitch → semitones
  const semitonesArr = pitchHistory.map(hzToSemitones);
  const pitchMean = semitonesArr.reduce((a, b) => a + b, 0) / semitonesArr.length;
  const pitchStd = Math.sqrt(
    semitonesArr.reduce((s, v) => s + (v - pitchMean) ** 2, 0) / semitonesArr.length
  );
  const pitchVar = pitchMean > 0 ? clamp(pitchStd / pitchMean, 0, 1) : 0;

  // Loudness (normalise RMS to 0-1 sone-like scale)
  const maxRms = 0.5; // typical max RMS for voice
  const loudArr = loudnessHistory.map(r => clamp(r / maxRms, 0, 1));
  const loudMean = loudArr.reduce((a, b) => a + b, 0) / loudArr.length;
  const loudStd = Math.sqrt(
    loudArr.reduce((s, v) => s + (v - loudMean) ** 2, 0) / loudArr.length
  );
  const loudVar = loudMean > 0 ? clamp(loudStd / loudMean, 0, 0.5) : 0;

  // Jitter (pitch period perturbation)
  let jitterSum = 0;
  for (let i = 1; i < pitchHistory.length; i++) {
    const p1 = 1 / pitchHistory[i - 1];
    const p2 = 1 / pitchHistory[i];
    jitterSum += Math.abs(p2 - p1);
  }
  const meanPeriod = pitchHistory.reduce((a, f) => a + 1 / f, 0) / pitchHistory.length;
  const jitter = meanPeriod > 0
    ? clamp((jitterSum / (pitchHistory.length - 1)) / meanPeriod, 0.005, 0.06)
    : 0.03;

  // Shimmer (amplitude perturbation in dB)
  let shimmerSum = 0;
  for (let i = 1; i < amplitudeHistory.length; i++) {
    const a1 = amplitudeHistory[i - 1];
    const a2 = amplitudeHistory[i];
    if (a1 > 0 && a2 > 0) {
      shimmerSum += Math.abs(20 * Math.log10(a2 / a1));
    }
  }
  const shimmer = amplitudeHistory.length > 1
    ? clamp(shimmerSum / (amplitudeHistory.length - 1), 0.3, 2.5)
    : 1.0;

  // Speech rate
  const speechRate = elapsedSec > 0 ? clamp(syllableCount / elapsedSec, 1, 6) : 3;

  // Pause ratio
  const pauseRatio = totalFrames > 0
    ? clamp((silentFrames / totalFrames) * 100, 5, 50)
    : 20;

  return { pitchMean, pitchVar, loudMean, loudVar, jitter, shimmer, speechRate, pauseRatio };
}

// ── Stop Recording ───────────────────────────────
function stopRecording() {
  isRecording = false;
  cancelAnimationFrame(animFrameId);
  clearInterval(timerInterval);

  // Stop mic
  if (micStream) {
    micStream.getTracks().forEach(t => t.stop());
    micStream = null;
  }
  if (audioCtx) {
    audioCtx.close();
    audioCtx = null;
  }

  // UI
  const btn = document.getElementById('btn-record');
  btn.textContent = '🎙️ Record Your Voice';
  btn.classList.remove('recording');
  document.getElementById('recording-status').classList.add('hidden');

  // Final results
  const results = computeResults();
  if (!results || pitchHistory.length < 5) {
    alert('Recording too short or no voice detected. Please speak for at least 5 seconds.');
    resetAll();
    return;
  }

  // Animate final meters
  const keys = Object.keys(results);
  keys.forEach((k, i) => setTimeout(() => setMeter(k, results[k]), i * 100));

  // Derived scores
  setTimeout(() => {
    setRing('tone', toneScore(results.pitchVar));
    setRing('confidence', confidenceScore(results.jitter, results.shimmer));
    setRing('pace', paceScore(results.speechRate, results.pauseRatio));
  }, keys.length * 100 + 200);
}

// ── Event Listeners ──────────────────────────────
document.getElementById('btn-record').addEventListener('click', () => {
  if (isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
});

document.getElementById('btn-demo').addEventListener('click', runDemo);
document.getElementById('btn-reset').addEventListener('click', resetAll);
