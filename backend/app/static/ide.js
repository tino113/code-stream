const state = {
  files: {
    'main.py': 'print("Hello from teacher")',
    'helpers.py': 'def greet(name):\n    return f"Hello {name}"\n',
  },
  currentFile: 'main.py',
  baseline: 'print("Hello from teacher")',
  diffMode: 'highlight',
  recording: false,
  startedAt: null,
  events: [],
  annotations: [],
  selectedTimelineIndex: null,
};

function nowMs() {
  if (!state.startedAt) return 0;
  return Date.now() - state.startedAt;
}

function addEvent(type, detail = {}) {
  if (!state.recording) return;
  state.events.push({ t: nowMs(), type, ...detail });
  renderTimeline();
}

function setOutput(text) {
  const out = document.getElementById('output');
  if (out) out.textContent = text;
}

async function runCode() {
  const editor = document.getElementById('editor');
  const code = editor?.value ?? '';
  if (editor && state.files[state.currentFile] !== undefined) {
    state.files[state.currentFile] = code;
  }

  const res = await fetch('/api/execute', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  });
  const data = await res.json();
  setOutput(`exit=${data.exit_code}\nstdout:\n${data.stdout || '(none)'}\nstderr:\n${data.stderr || '(none)'}`);
  addEvent('run', { file: state.currentFile, exit_code: data.exit_code });
}

async function getHint() {
  const code = document.getElementById('editor')?.value ?? '';
  const output = document.getElementById('output')?.textContent ?? '';
  const hint = document.getElementById('hint');
  if (!hint) return;

  const res = await fetch('/api/debug', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, error_message: output }),
  });

  const data = await res.json();
  hint.textContent = data.guidance;
}

function renderDiff() {
  const view = document.getElementById('change-view');
  const editor = document.getElementById('editor');
  if (!view || !editor) return;

  const before = state.baseline.split('\n');
  const after = editor.value.split('\n');
  const max = Math.max(before.length, after.length);
  const html = [];

  for (let i = 0; i < max; i += 1) {
    const prev = before[i] ?? '';
    const next = after[i] ?? '';
    if (prev === next) {
      const cls = state.diffMode === 'dim' ? 'diff-unchanged dimmed' : 'diff-unchanged';
      html.push(`<div class="${cls}"> ${escapeHtml(next)}</div>`);
    } else {
      if (prev) html.push(`<div class="diff-removed">- ${escapeHtml(prev)}</div>`);
      if (next) html.push(`<div class="diff-added">+ ${escapeHtml(next)}</div>`);
    }
  }

  view.innerHTML = html.join('') || 'No code yet.';
}

function escapeHtml(value) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function renderTimeline() {
  const timeline = document.getElementById('timeline');
  if (!timeline) return;

  timeline.innerHTML = '';
  state.events.forEach((event, idx) => {
    const li = document.createElement('li');
    li.textContent = `[${(event.t / 1000).toFixed(2)}s] ${event.type} ${event.file || ''}`;
    if (idx === state.selectedTimelineIndex) li.classList.add('selected');
    li.addEventListener('click', () => {
      state.selectedTimelineIndex = idx;
      renderTimeline();
    });
    timeline.appendChild(li);
  });
}

function switchFile(fileName) {
  const editor = document.getElementById('editor');
  if (!editor || !state.files[fileName]) return;

  state.files[state.currentFile] = editor.value;
  state.currentFile = fileName;
  editor.value = state.files[fileName];
  document.querySelectorAll('.file-btn').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.file === fileName);
  });

  addEvent('file_switch', { file: fileName });
  renderDiff();
}

function startRecording() {
  state.recording = true;
  state.startedAt = Date.now();
  state.events = [];
  state.annotations = [];
  state.selectedTimelineIndex = null;
  addEvent('recording_start', { file: state.currentFile });
}

function stopRecording() {
  addEvent('recording_stop', { file: state.currentFile });
  state.recording = false;
}

function addAnnotation() {
  const input = document.getElementById('annotation-text');
  if (!input || !input.value.trim()) return;
  const annotation = { t: nowMs(), text: input.value.trim(), file: state.currentFile };
  state.annotations.push(annotation);
  addEvent('annotation', annotation);
  input.value = '';
}

function trimPauses() {
  if (state.events.length < 2) return;

  let offset = 0;
  const trimmed = state.events.map((event, index) => {
    if (index === 0) return { ...event };
    const prev = state.events[index - 1];
    const gap = event.t - prev.t;
    if (gap > 3000) offset += gap - 1000;
    return { ...event, t: event.t - offset };
  });

  state.events = trimmed;
  renderTimeline();
}

function removeSelectedEvent() {
  if (state.selectedTimelineIndex == null) return;
  state.events.splice(state.selectedTimelineIndex, 1);
  state.selectedTimelineIndex = null;
  renderTimeline();
}

async function saveRecording() {
  const title = `Lesson ${new Date().toISOString().slice(0, 19)}`;
  const res = await fetch('/api/recordings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title,
      created_by: 'teacher@local',
      events: state.events,
      annotations: state.annotations,
    }),
  });
  const data = await res.json();
  setOutput(`Saved recording #${data.id} (${state.events.length} events, ${state.annotations.length} annotations)`);
}

function playTimeline() {
  const speed = Number(document.getElementById('playback-speed')?.value || '1');
  if (!state.events.length) return;

  setOutput(`Playing ${state.events.length} events at ${speed}x`);
  let last = 0;
  state.events.forEach((event) => {
    const wait = (event.t - last) / speed;
    last = event.t;
    setTimeout(() => {
      setOutput(`Playback @ ${(event.t / 1000).toFixed(2)}s -> ${event.type} (${event.file || state.currentFile})`);
    }, Math.max(0, wait));
  });
}

function bindTeacherFeatures() {
  document.getElementById('start-recording')?.addEventListener('click', startRecording);
  document.getElementById('stop-recording')?.addEventListener('click', stopRecording);
  document.getElementById('save-recording')?.addEventListener('click', saveRecording);
  document.getElementById('add-annotation')?.addEventListener('click', addAnnotation);
  document.getElementById('trim-pauses')?.addEventListener('click', trimPauses);
  document.getElementById('remove-selected')?.addEventListener('click', removeSelectedEvent);
  document.getElementById('play-timeline')?.addEventListener('click', playTimeline);
  document.getElementById('capture-baseline')?.addEventListener('click', () => {
    state.baseline = document.getElementById('editor')?.value || '';
    renderDiff();
  });
  document.getElementById('mode-highlight')?.addEventListener('click', () => {
    state.diffMode = 'highlight';
    renderDiff();
  });
  document.getElementById('mode-dim')?.addEventListener('click', () => {
    state.diffMode = 'dim';
    renderDiff();
  });

  document.querySelectorAll('.file-btn').forEach((btn) => {
    btn.addEventListener('click', () => switchFile(btn.dataset.file));
  });

  document.getElementById('editor')?.addEventListener('input', () => {
    addEvent('edit', { file: state.currentFile, chars: document.getElementById('editor')?.value.length || 0 });
    renderDiff();
  });

  renderDiff();
}

window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('run')?.addEventListener('click', runCode);
  document.getElementById('debug')?.addEventListener('click', getHint);

  if (document.getElementById('start-recording')) {
    bindTeacherFeatures();
  }
});
