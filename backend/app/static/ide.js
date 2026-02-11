let isPlaying = false;
let currentTime = 0;
let currentCheckpoint = null;
let playbackTimer = null;
let playbackState = { checkpoint_states: {} };
let usedHintInLoop = false;

const playBtn = document.getElementById("play-btn");
const timeDisplay = document.getElementById("time-display");
const panel = document.getElementById("challenge-panel");
const promptEl = document.getElementById("challenge-prompt");
const tagsEl = document.getElementById("challenge-tags");
const unlockEl = document.getElementById("challenge-unlock");
const statusEl = document.getElementById("status");

const runBtn = document.getElementById("run-btn");
const debugBtn = document.getElementById("debug-btn");
const hintBtn = document.getElementById("hint-btn");
const passBtn = document.getElementById("pass-btn");
const unlockBtn = document.getElementById("unlock-btn");

async function fetchPlaybackState() {
  const response = await fetch(`/api/student/${window.STUDENT_ID}/playback`);
  playbackState = await response.json();
}

function updateTimeUI() {
  timeDisplay.textContent = `${currentTime.toFixed(1)}s`;
}

function checkpointState(checkpointId) {
  return playbackState.checkpoint_states[checkpointId] || { status: "assigned" };
}

function shouldInterruptAt(checkpoint) {
  const state = checkpointState(checkpoint.id);
  return ["assigned", "attempted", "passed"].includes(state.status) && currentTime >= checkpoint.timestamp;
}

function interruptForCheckpoint(checkpoint) {
  isPlaying = false;
  clearInterval(playbackTimer);
  currentCheckpoint = checkpoint;
  usedHintInLoop = false;

  promptEl.textContent = checkpoint.prompt;
  tagsEl.textContent = checkpoint.expected_concept_tags.join(", ");
  unlockEl.textContent = checkpoint.unlock_condition;
  panel.classList.add("active");
  statusEl.textContent = `Playback paused at ${checkpoint.timestamp}s for checkpoint.`;
}

async function postCheckpointAction(action, extra = {}) {
  if (!currentCheckpoint) return;

  const response = await fetch(
    `/api/student/${window.STUDENT_ID}/checkpoints/${currentCheckpoint.id}/state`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, ...extra }),
    },
  );

  const data = await response.json();
  playbackState.checkpoint_states[currentCheckpoint.id] = data;
  return data;
}

function tickPlayback() {
  currentTime += 0.5;
  updateTimeUI();

  const nextCheckpoint = window.CHECKPOINTS.find((cp) => shouldInterruptAt(cp));
  if (nextCheckpoint) {
    interruptForCheckpoint(nextCheckpoint);
  }
}

playBtn.addEventListener("click", () => {
  if (isPlaying) return;
  panel.classList.remove("active");
  isPlaying = true;
  playbackTimer = setInterval(tickPlayback, 500);
});

runBtn.addEventListener("click", async () => {
  const runtimeSuccess = Math.random() > 0.3;
  const state = await postCheckpointAction("attempt", {
    used_hint: usedHintInLoop,
    runtime_success: runtimeSuccess,
  });
  statusEl.textContent = runtimeSuccess
    ? `Run succeeded. Attempts: ${state.attempt_count}.`
    : `Run failed. Attempts: ${state.attempt_count}.`;
});

debugBtn.addEventListener("click", async () => {
  const runtimeSuccess = true;
  const state = await postCheckpointAction("attempt", {
    used_hint: usedHintInLoop,
    runtime_success: runtimeSuccess,
  });
  statusEl.textContent = `Debug loop completed. Attempts: ${state.attempt_count}. Runtime success recorded.`;
});

hintBtn.addEventListener("click", () => {
  usedHintInLoop = true;
  statusEl.textContent = "Hint consumed for this challenge loop.";
});

passBtn.addEventListener("click", async () => {
  await postCheckpointAction("pass");
  statusEl.textContent = "Checkpoint marked passed. You can unlock playback now.";
});

unlockBtn.addEventListener("click", async () => {
  const state = await postCheckpointAction("unlock");
  panel.classList.remove("active");
  statusEl.textContent = `Checkpoint ${state.status}. Playback resumed.`;
  currentCheckpoint = null;
  playBtn.click();
});

fetchPlaybackState();
updateTimeUI();
