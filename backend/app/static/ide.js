const state = {
  recording: {
    id: "demo-recording",
    active_branch: "main",
    branch_events: { main: [] },
    branch_parents: { main: null },
    events: [],
  },
  pendingIntent: "",
};

function eventLookup(recording) {
  return Object.fromEntries((recording.events || []).map((event) => [event.id, event]));
}

function resolveBranchPath(recording, branchName, terminalEventId = null) {
  const branchEvents = recording.branch_events || {};
  const branchParents = recording.branch_parents || {};
  if (!branchEvents[branchName]) {
    throw new Error(`Unknown branch: ${branchName}`);
  }

  const lineage = [];
  const seen = new Set();
  let current = branchName;
  while (current) {
    if (seen.has(current)) {
      throw new Error("Branch cycle detected");
    }
    seen.add(current);
    lineage.push(current);
    current = branchParents[current];
  }
  lineage.reverse();

  const orderedIds = [];
  lineage.forEach((name) => {
    (branchEvents[name] || []).forEach((eventId) => {
      if (!orderedIds.includes(eventId)) {
        orderedIds.push(eventId);
      }
    });
  });

  const lookup = eventLookup(recording);
  const events = [];
  for (const eventId of orderedIds) {
    if (lookup[eventId]) {
      events.push(lookup[eventId]);
    }
    if (terminalEventId && eventId === terminalEventId) {
      break;
    }
  }

  return events;
}

function renderBranches() {
  const branchNames = Object.keys(state.recording.branch_events);
  const branchSelect = document.getElementById("branch-select");
  const mergeSelect = document.getElementById("merge-source");

  [branchSelect, mergeSelect].forEach((select) => {
    select.innerHTML = "";
    branchNames.forEach((name) => {
      const option = document.createElement("option");
      option.value = name;
      option.innerText = name;
      if (name === state.recording.active_branch && select.id === "branch-select") {
        option.selected = true;
      }
      select.appendChild(option);
    });
  });
}

function renderTimeline() {
  const list = document.getElementById("timeline-events");
  list.innerHTML = "";
  const events = resolveBranchPath(state.recording, state.recording.active_branch);
  events.forEach((event) => {
    const item = document.createElement("li");
    const intent = event.intent ? ` [intent: ${event.intent}]` : "";
    item.innerText = `${event.id} @${event.branch_name}${intent}`;
    list.appendChild(item);
  });
}

function updateStatus(text) {
  document.getElementById("status").innerText = text;
}

function createEvent(branchName) {
  const event = {
    id: crypto.randomUUID(),
    branch_name: branchName,
    parent_event_id: null,
    intent: state.pendingIntent,
    timestamp: new Date().toISOString(),
  };
  state.pendingIntent = "";
  state.recording.events.push(event);
  if (!state.recording.branch_events[branchName]) {
    state.recording.branch_events[branchName] = [];
  }
  state.recording.branch_events[branchName].push(event.id);
  return event;
}

function bindControls() {
  document.getElementById("create-branch").addEventListener("click", () => {
    const input = document.getElementById("new-branch-name");
    const name = input.value.trim();
    if (!name || state.recording.branch_events[name]) {
      updateStatus("Branch name missing or already exists");
      return;
    }

    const parentBranch = state.recording.active_branch;
    state.recording.branch_events[name] = [];
    state.recording.branch_parents[name] = parentBranch;
    state.recording.active_branch = name;

    renderBranches();
    renderTimeline();
    updateStatus(`Created and switched to branch '${name}' from '${parentBranch}'`);
  });

  document.getElementById("switch-branch").addEventListener("click", () => {
    const selected = document.getElementById("branch-select").value;
    state.recording.active_branch = selected;
    renderTimeline();
    updateStatus(`Switched to branch '${selected}'`);
  });

  document.getElementById("merge-branch").addEventListener("click", () => {
    const source = document.getElementById("merge-source").value;
    const target = state.recording.active_branch;
    if (source === target) {
      updateStatus("Choose a different source branch");
      return;
    }

    const existing = new Set(state.recording.branch_events[target] || []);
    (state.recording.branch_events[source] || []).forEach((id) => {
      if (!existing.has(id)) {
        state.recording.branch_events[target].push(id);
      }
    });

    renderTimeline();
    updateStatus(`Merged '${source}' into '${target}'`);
  });

  document.getElementById("save-intent").addEventListener("click", () => {
    const intentInput = document.getElementById("intent-label");
    state.pendingIntent = intentInput.value.trim();
    const event = createEvent(state.recording.active_branch);
    renderTimeline();
    updateStatus(`Created event '${event.id}' on '${event.branch_name}' with intent '${event.intent || "none"}'`);
    intentInput.value = "";
  });
}

bindControls();
renderBranches();
renderTimeline();
