const stageList = document.getElementById('hint-stages');
const meta = document.getElementById('hint-meta');

function renderStageChecklist(response) {
  stageList.innerHTML = '';
  meta.textContent = `Hint level: ${response.hint_level} | Repeat count: ${response.repeated_error_count}`;

  response.stages.forEach((entry, index) => {
    const item = document.createElement('li');
    item.className = index === 0 ? '' : 'completed';

    const heading = document.createElement('strong');
    heading.textContent = `${index + 1}. ${entry.stage.replace('_', ' ')}`;

    const body = document.createElement('p');
    body.textContent = entry.content;

    item.appendChild(heading);
    item.appendChild(body);
    stageList.appendChild(item);
  });
}

async function requestHints(event) {
  event.preventDefault();

  const payload = {
    student_id: document.getElementById('student-id').value,
    error: document.getElementById('error').value,
    attempted_fix: document.getElementById('attempted-fix').value || null,
  };

  const response = await fetch('/api/debug', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  const data = await response.json();
  if (!response.ok) {
    meta.textContent = `Unable to provide hints: ${data.detail || 'Unknown error'}`;
    stageList.innerHTML = '';
    return;
  }

  renderStageChecklist(data);
}

document.getElementById('debug-form').addEventListener('submit', requestHints);
