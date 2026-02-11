# Code Stream

## Feature Matrix

| Feature | Status | Notes |
| --- | --- | --- |
| Recording event capture | ✅ | Events are persisted per recording. |
| Scene-layer metadata | ✅ | Per recording `scenes_json` stores focus range, zoom, spotlight blocks, and transition type. |
| Teacher scene controls UI | ✅ | `teacher.html` and `ide.js` include controls to author scene metadata. |
| Render plan generation | ✅ | `/api/render-jobs` accepts optional `scene_metadata` and returns computed `render_plan`. |
| Render payload validation | ✅ | Scene payload fields are validated before job queueing. |

## Local testing

```bash
pytest -q
```
