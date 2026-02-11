const ATLAS_MARKER_CLASS = "atlas-concept-marker";

export async function loadCodeAtlas(files) {
  const response = await fetch("/api/code-atlas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ files }),
  });

  if (!response.ok) {
    throw new Error(`Atlas request failed: ${response.status}`);
  }

  return response.json();
}

export function ensureAtlasPanel(container) {
  let panel = container.querySelector("#atlas-panel");
  if (!panel) {
    panel = document.createElement("section");
    panel.id = "atlas-panel";
    panel.style.borderLeft = "1px solid #2d2d2d";
    panel.style.padding = "8px";
    panel.style.overflowY = "auto";
    panel.style.maxHeight = "100%";
    panel.innerHTML = "<h3>Code Atlas</h3><div class='atlas-clusters'></div>";
    container.appendChild(panel);
  }
  return panel;
}

export function renderAtlasPanel({ panel, atlas, editor, activeFile }) {
  const clustersContainer = panel.querySelector(".atlas-clusters");
  clustersContainer.innerHTML = "";

  const nodesById = new Map(atlas.nodes.map((node) => [node.id, node]));

  Object.entries(atlas.clusters).forEach(([clusterName, nodeIds]) => {
    const clusterSection = document.createElement("div");
    const title = document.createElement("h4");
    title.textContent = `${clusterName} (${nodeIds.length})`;
    clusterSection.appendChild(title);

    const list = document.createElement("ul");
    nodeIds.forEach((nodeId) => {
      const node = nodesById.get(nodeId);
      if (!node || node.file !== activeFile) return;

      const item = document.createElement("li");
      const jumpButton = document.createElement("button");
      jumpButton.type = "button";
      jumpButton.textContent = `${node.kind}: ${node.identifier} [${node.start_line}-${node.end_line}]`;
      jumpButton.onclick = () => {
        editor.revealLineInCenter(node.start_line);
        editor.setSelection({
          startLineNumber: node.start_line,
          startColumn: 1,
          endLineNumber: node.end_line,
          endColumn: 1,
        });
        editor.focus();
      };
      item.appendChild(jumpButton);
      list.appendChild(item);
    });

    if (list.children.length > 0) {
      clusterSection.appendChild(list);
      clustersContainer.appendChild(clusterSection);
    }
  });
}

export function applyAtlasMarkers(editor, atlas, activeFile, previousDecorations = []) {
  const model = editor.getModel();
  if (!model) return previousDecorations;

  const decorations = atlas.nodes
    .filter((node) => node.file === activeFile && node.kind !== "file")
    .map((node) => ({
      range: new monaco.Range(node.start_line, 1, node.end_line, 1),
      options: {
        description: `atlas:${node.kind}`,
        className: ATLAS_MARKER_CLASS,
        minimap: {
          color: markerColor(node.kind),
          position: monaco.editor.MinimapPosition.Inline,
        },
        stickiness: monaco.editor.TrackedRangeStickiness.NeverGrowsWhenTypingAtEdges,
      },
    }));

  return editor.deltaDecorations(previousDecorations, decorations);
}

function markerColor(kind) {
  switch (kind) {
    case "class":
      return "#4caf50";
    case "function":
    case "async_function":
      return "#2196f3";
    case "loop":
      return "#ff9800";
    case "exception":
      return "#f44336";
    case "io_call":
      return "#9c27b0";
    default:
      return "#607d8b";
  }
}
