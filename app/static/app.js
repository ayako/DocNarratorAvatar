/**
 * DocNarratorAvatar – frontend application
 *
 * State machine:  UPLOAD → PROCESSING → READY → PLAYING
 *                                      ↘ ERROR
 */

/* ── DOM references ─────────────────────────────────────────────────────── */

const uploadPanel     = document.getElementById('upload-panel');
const processingPanel = document.getElementById('processing-panel');
const resultPanel     = document.getElementById('result-panel');
const errorPanel      = document.getElementById('error-panel');

const dropZone        = document.getElementById('drop-zone');
const fileInput       = document.getElementById('file-input');
const selectedFile    = document.getElementById('selected-file');
const uploadBtn       = document.getElementById('upload-btn');

const progressFill    = document.getElementById('progress-fill');
const progressStep    = document.getElementById('progress-step');
const stepEls         = [
  document.getElementById('step-1'),
  document.getElementById('step-2'),
  document.getElementById('step-3'),
];

const playCta         = document.getElementById('play-cta');
const playBtn         = document.getElementById('play-btn');
const playerArea      = document.getElementById('player-area');
const avatarVideo     = document.getElementById('avatar-video');
const captionOverlay  = document.getElementById('caption-overlay');
const keyPointsList   = document.getElementById('key-points-list');

const scriptArea      = document.getElementById('script-area');
const scriptText      = document.getElementById('script-text');
const scriptCaptions  = document.getElementById('script-captions-list');

const restartBtn      = document.getElementById('restart-btn');
const retryBtn        = document.getElementById('retry-btn');
const errorMsg        = document.getElementById('error-msg');

/* ── Application state ──────────────────────────────────────────────────── */

let jobId        = null;
let captions     = [];
let pollTimer    = null;
let selectedFl   = null;

/* ── Upload UI ──────────────────────────────────────────────────────────── */

dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('keydown', e => {
  if (e.key === 'Enter' || e.key === ' ') fileInput.click();
});

dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer?.files?.[0];
  if (file) setFile(file);
});

fileInput.addEventListener('change', () => {
  const file = fileInput.files?.[0];
  if (file) setFile(file);
});

function setFile(file) {
  selectedFl = file;
  selectedFile.textContent = `✔ ${file.name}  (${formatBytes(file.size)})`;
  uploadBtn.disabled = false;
}

uploadBtn.addEventListener('click', startUpload);

/* ── Upload & processing ────────────────────────────────────────────────── */

async function startUpload() {
  if (!selectedFl) return;

  const form = new FormData();
  form.append('file', selectedFl);

  uploadBtn.disabled = true;
  show(processingPanel);
  hide(uploadPanel);

  try {
    const resp = await fetch('/api/process', { method: 'POST', body: form });
    if (!resp.ok) throw new Error(`サーバーエラー: ${resp.status}`);
    const data = await resp.json();
    jobId = data.job_id;
    pollTimer = setInterval(pollStatus, 2000);
  } catch (err) {
    showError(err.message);
  }
}

async function pollStatus() {
  try {
    const resp = await fetch(`/api/status/${jobId}`);
    if (!resp.ok) throw new Error(`ステータス取得エラー: ${resp.status}`);
    const data = await resp.json();

    updateProgress(data.progress, data.step);

    if (data.status === 'completed') {
      clearInterval(pollTimer);
      await loadResult();
    } else if (data.status === 'failed') {
      clearInterval(pollTimer);
      showError(data.error || '処理に失敗しました');
    }
  } catch (err) {
    clearInterval(pollTimer);
    showError(err.message);
  }
}

function updateProgress(pct, stepText) {
  progressFill.style.width = `${pct}%`;
  progressFill.closest('[role=progressbar]').setAttribute('aria-valuenow', pct);
  progressStep.textContent = stepText;

  // Activate step indicators based on progress
  const thresholds = [10, 35, 60];
  thresholds.forEach((threshold, i) => {
    const el = stepEls[i];
    el.classList.remove('active', 'done');
    if (pct > threshold + 25) {
      el.classList.add('done');
    } else if (pct >= threshold) {
      el.classList.add('active');
    }
  });
}

/* ── Result display ─────────────────────────────────────────────────────── */

async function loadResult() {
  const resp = await fetch(`/api/result/${jobId}`);
  if (!resp.ok) { showError('結果の取得に失敗しました'); return; }
  const data = await resp.json();

  captions = data.captions || [];

  hide(processingPanel);
  show(resultPanel);

  if (data.has_video) {
    // Show play-CTA; video loads on play button click
    avatarVideo.src = data.video_url;
    buildKeyPoints(keyPointsList, captions);
    playBtn.addEventListener('click', startPlayback, { once: true });
  } else {
    // Fallback: show script + captions as text
    hide(playCta);
    scriptText.textContent = data.script || '（スクリプトなし）';
    buildKeyPoints(scriptCaptions, captions);
    show(scriptArea);
  }
}

function buildKeyPoints(listEl, items) {
  listEl.innerHTML = '';
  items.forEach(text => {
    const li = document.createElement('li');
    li.textContent = text;
    listEl.appendChild(li);
  });
}

/* ── Playback ───────────────────────────────────────────────────────────── */

function startPlayback() {
  hide(playCta);
  show(playerArea);
  avatarVideo.play().catch(() => {/* autoplay may be blocked */});
  avatarVideo.addEventListener('timeupdate', syncCaptions);
  avatarVideo.addEventListener('ended', () => {
    captionOverlay.textContent = '';
    highlightKeyPoint(-1);
  });
}

function syncCaptions() {
  if (!captions.length || !avatarVideo.duration) return;
  const idx = Math.min(
    Math.floor(avatarVideo.currentTime / avatarVideo.duration * captions.length),
    captions.length - 1
  );
  captionOverlay.textContent = captions[idx];
  highlightKeyPoint(idx);
}

function highlightKeyPoint(activeIdx) {
  keyPointsList.querySelectorAll('li').forEach((li, i) => {
    li.classList.toggle('active', i === activeIdx);
  });
}

/* ── Error panel ────────────────────────────────────────────────────────── */

function showError(msg) {
  hide(uploadPanel);
  hide(processingPanel);
  hide(resultPanel);
  errorMsg.textContent = msg;
  show(errorPanel);
}

retryBtn.addEventListener('click', resetApp);
restartBtn.addEventListener('click', resetApp);

function resetApp() {
  clearInterval(pollTimer);
  jobId      = null;
  captions   = [];
  selectedFl = null;

  // Reset upload panel
  fileInput.value         = '';
  selectedFile.textContent = '';
  uploadBtn.disabled      = true;

  // Reset processing panel
  progressFill.style.width = '0%';
  progressStep.textContent = '';
  stepEls.forEach(el => el.classList.remove('active', 'done'));

  // Reset result panel
  show(playCta);
  hide(playerArea);
  hide(scriptArea);
  avatarVideo.pause();
  avatarVideo.src            = '';
  captionOverlay.textContent = '';
  keyPointsList.innerHTML    = '';
  scriptText.textContent     = '';
  scriptCaptions.innerHTML   = '';

  hide(processingPanel);
  hide(resultPanel);
  hide(errorPanel);
  show(uploadPanel);
}

/* ── Utility ────────────────────────────────────────────────────────────── */

function show(el) { if (el) el.classList.remove('hidden'); }
function hide(el) { if (el) el.classList.add('hidden'); }

function formatBytes(bytes) {
  if (bytes < 1024)       return `${bytes} B`;
  if (bytes < 1048576)    return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}
