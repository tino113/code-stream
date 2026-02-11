async function runCode() {
  const code = document.getElementById('editor')?.value ?? '';
  const output = document.getElementById('output');
  const hint = document.getElementById('hint');
  if (hint) hint.textContent = 'Debug hints appear here.';

  const res = await fetch('/api/execute', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  });
  const data = await res.json();
  output.textContent = `exit=${data.exit_code}\nstdout:\n${data.stdout || '(none)'}\nstderr:\n${data.stderr || '(none)'}`;
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

window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('run')?.addEventListener('click', runCode);
  document.getElementById('debug')?.addEventListener('click', getHint);
});
