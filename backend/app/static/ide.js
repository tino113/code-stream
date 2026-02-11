const state = {
  files: {
    'main.py': 'def greet(name):\n    return f"Hello, {name}!"\n\nprint(greet("CodeStream"))\n',
    'helpers.py': 'def normalize_input(text):\n    return text.strip().lower()\n',
  },
  currentFile: 'main.py',
  baseline: '',
  diffMode: 'highlight',
  recording: false,
  startedAt: null,
  events: [],
  annotations: [],
  selectedTimelineIndex: null,
  showWhitespace: false,
  editorTheme: 'vs-dark',
  editorFontSize: 14,
  monacoEditor: null,
};

function nowMs() {
  if (!state.startedAt) return 0;
  return Date.now() - state.startedAt;
}

function currentCode() {
  if (state.monacoEditor) return state.monacoEditor.getValue();
  const fallback = document.getElementById('editor');
  return fallback?.value ?? '';
}

function setCode(value) {
  if (state.monacoEditor) {
    state.monacoEditor.setValue(value);
    return;
  }
  const fallback = document.getElementById('editor');
  if (fallback) fallback.value = value;
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
  const code = currentCode();
  state.files[state.currentFile] = code;

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
  const code = currentCode();
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
  if (!view) return;

  const before = (state.baseline || '').split('\n');
  const after = currentCode().split('\n');
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
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');
}

function renderTimeline() {
  const timeline = document.getElementById('timeline');
  if (!timeline) return;

  timeline.innerHTML = '';
  state.events.forEach((event, idx) => {
    const li = document.createElement('li');
    li.textContent = `[${(event.t / 1000).toFixed(2)}s] ${event.type}${event.file ? ` · ${event.file}` : ''}`;
    if (idx === state.selectedTimelineIndex) li.classList.add('selected');
    li.addEventListener('click', () => {
      state.selectedTimelineIndex = idx;
      renderTimeline();
    });
    timeline.appendChild(li);
  });
}

function switchFile(fileName) {
  if (!(fileName in state.files)) return;
  state.files[state.currentFile] = currentCode();
  state.currentFile = fileName;
  setCode(state.files[fileName]);

  document.querySelectorAll('.file-btn').forEach((btn) => btn.classList.toggle('active', btn.dataset.file === fileName));
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
  state.events = state.events.map((event, index) => {
    if (index === 0) return { ...event };
    const prev = state.events[index - 1];
    const gap = event.t - prev.t;
    if (gap > 3000) offset += gap - 1000;
    return { ...event, t: event.t - offset };
  });
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
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, created_by: 'teacher@local', events: state.events, annotations: state.annotations }),
  });
  const data = await res.json();
  setOutput(`Saved recording #${data.id} (${state.events.length} events, ${state.annotations.length} annotations)`);
}

async function suggestAnnotations() {
  const recordingIdText = (document.getElementById('output')?.textContent || '').match(/Saved recording #(\d+)/)?.[1];
  if (!recordingIdText) {
    setOutput('Save a recording first, then request AI suggestions.');
    return;
  }

  const res = await fetch(`/api/recordings/${recordingIdText}/suggest-annotations`);
  const data = await res.json();
  state.annotations = data.suggestions || [];
  setOutput(`AI suggested ${state.annotations.length} markers. Add/adjust them as needed.`);
}

function playTimeline() {
  const speed = Number(document.getElementById('playback-speed')?.value || '1');
  if (!state.events.length) return;

  setOutput(`Playing ${state.events.length} events at ${speed}x`);
  state.events.forEach((event) => {
    const delay = event.t / speed;
    setTimeout(() => {
      setOutput(`Playback @ ${(event.t / 1000).toFixed(2)}s -> ${event.type}${event.file ? ` (${event.file})` : ''}`);
    }, Math.max(0, delay));
  });
}

function toggleTheme() {
  document.body.classList.toggle('dark-mode');
  state.editorTheme = state.editorTheme === 'vs-dark' ? 'vs' : 'vs-dark';
  if (state.monacoEditor && window.monaco) {
    window.monaco.editor.setTheme(state.editorTheme);
  }
}

function toggleWhitespace() {
  state.showWhitespace = !state.showWhitespace;
  if (state.monacoEditor) {
    state.monacoEditor.updateOptions({ renderWhitespace: state.showWhitespace ? 'all' : 'none' });
  }
}

function setFontSize() {
  const value = Number(document.getElementById('font-size')?.value || '14');
  state.editorFontSize = value;
  if (state.monacoEditor) state.monacoEditor.updateOptions({ fontSize: value });
}

function initMonacoEditor() {
  const container = document.getElementById('editor');
  if (!container || !window.require) return;

  window.require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs' } });
  window.require(['vs/editor/editor.main'], () => {
    state.monacoEditor = window.monaco.editor.create(container, {
      value: state.files[state.currentFile],
      language: 'python',
      theme: state.editorTheme,
      fontSize: state.editorFontSize,
      minimap: { enabled: true },
      automaticLayout: true,
      renderWhitespace: 'none',
      smoothScrolling: true,
      roundedSelection: true,
      padding: { top: 12 },
    });

    state.baseline = state.monacoEditor.getValue();
    state.monacoEditor.onDidChangeModelContent(() => {
      addEvent('edit', { file: state.currentFile, chars: currentCode().length });
      renderDiff();
    });
    renderDiff();
  });
}

async function registerAndLogin(action) {
  const email = document.getElementById('email')?.value || '';
  const password = document.getElementById('password')?.value || '';
  const role = document.getElementById('role')?.value || 'student';
  const output = document.getElementById('auth-output');
  if (!output) return;

  if (action === 'register') {
    const reg = await fetch('/api/auth/register', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password, role }),
    });
    output.textContent = `Register: ${reg.status}`;
    return;
  }

  const login = await fetch('/api/auth/login', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }),
  });
  const data = await login.json();
  output.textContent = login.ok ? `Login successful as ${data.role}.` : `Login failed: ${data.detail || 'Unknown error'}`;
  if (login.ok) window.location.href = data.role === 'teacher' ? '/teacher' : '/student';
}

function bindTeacherFeatures() {
  document.getElementById('start-recording')?.addEventListener('click', startRecording);
  document.getElementById('stop-recording')?.addEventListener('click', stopRecording);
  document.getElementById('save-recording')?.addEventListener('click', saveRecording);
  document.getElementById('add-annotation')?.addEventListener('click', addAnnotation);
  document.getElementById('trim-pauses')?.addEventListener('click', trimPauses);
  document.getElementById('remove-selected')?.addEventListener('click', removeSelectedEvent);
  document.getElementById('play-timeline')?.addEventListener('click', playTimeline);
  document.getElementById('capture-baseline')?.addEventListener('click', () => { state.baseline = currentCode(); renderDiff(); });
  document.getElementById('mode-highlight')?.addEventListener('click', () => { state.diffMode = 'highlight'; renderDiff(); });
  document.getElementById('mode-dim')?.addEventListener('click', () => { state.diffMode = 'dim'; renderDiff(); });
  document.getElementById('toggle-whitespace')?.addEventListener('click', toggleWhitespace);
  document.getElementById('suggest-annotations')?.addEventListener('click', suggestAnnotations);
  document.querySelectorAll('.file-btn').forEach((btn) => btn.addEventListener('click', () => switchFile(btn.dataset.file)));
}

window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('run')?.addEventListener('click', runCode);
  document.getElementById('debug')?.addEventListener('click', getHint);
  document.getElementById('theme-toggle')?.addEventListener('click', toggleTheme);
  document.getElementById('font-size')?.addEventListener('change', setFontSize);
  document.getElementById('register-btn')?.addEventListener('click', () => registerAndLogin('register'));
  document.getElementById('login-btn')?.addEventListener('click', () => registerAndLogin('login'));

  if (document.getElementById('start-recording')) bindTeacherFeatures();
  initMonacoEditor();
});
