(() => {
  const scenes = [];

  const focusStart = document.getElementById("focus-start");
  const focusEnd = document.getElementById("focus-end");
  const zoomLevel = document.getElementById("zoom-level");
  const spotlightBlocks = document.getElementById("spotlight-blocks");
  const transitionType = document.getElementById("transition-type");
  const addSceneBtn = document.getElementById("add-scene");
  const scenePreview = document.getElementById("scene-preview");

  if (!addSceneBtn) return;

  function renderScenePreview() {
    scenePreview.textContent = JSON.stringify(scenes, null, 2);
  }

  function currentSceneFromControls() {
    return {
      focus_line_range: [Number(focusStart.value), Number(focusEnd.value)],
      zoom_level: Number(zoomLevel.value),
      spotlight_blocks: spotlightBlocks.value
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean),
      transition_type: transitionType.value,
    };
  }

  addSceneBtn.addEventListener("click", () => {
    scenes.push(currentSceneFromControls());
    renderScenePreview();
  });

  window.teacherSceneState = {
    getScenes: () => scenes.slice(),
    clearScenes: () => {
      scenes.length = 0;
      renderScenePreview();
    },
  };

  renderScenePreview();
})();
