# CodeStream - Phase 3 (Dark Mode + Advanced Media Pipeline Foundations)

This build adds a dark-first interface and introduces Phase 3 backend capabilities for rendering, voiceover generation, and auto-sync planning.

## Implemented

### UI / UX
- Bootstrap 5 + Monaco editor interfaces
- **Dark mode default** on all pages
- Theme selector with light / dark / high-contrast
- Monaco minimap, font-size control, whitespace visibility toggle

### Teacher IDE (Phase 2 + 3)
- Live recording of edits/run/file-switch events
- Timeline editing (trim pauses, remove events, playback speed)
- Manual annotation markers + suggestion endpoint integration
- **Phase 3 actions**:
  - generate TTS voiceover
  - auto-sync voiceover chunks to timeline anchors
  - create render jobs for final video output

### Student IDE
- Simplified Monaco IDE
- Run code and receive no-code-output debug guidance

### Backend APIs
- Auth: register/login
- Execution: `/api/execute`
- Debug guidance: `/api/debug`
- Recordings: create/list/get + suggest annotations
- **Phase 3 media APIs**:
  - `POST /api/render-jobs`
  - `GET /api/render-jobs/{id}`
  - `POST /api/voiceover/tts`
  - `POST /api/voiceover/auto-sync`


## UI benchmark notes (what we changed)

The IDE layout has been redesigned using common patterns from modern web IDEs (e.g., VS Code Web / GitHub Codespaces / Replit style layouts):
- activity rail on the far left for primary work modes
- persistent explorer sidebar for files and controls
- tab-like editor header and bottom status bar
- split inspector panels for timeline/change-preview/output
- darker, lower-contrast surfaces with clearer accent hierarchy

This preserves functionality while making the interface feel closer to production online IDE experiences.

## Phase check against product description

### Covered now
- ✅ Teacher/student web access with login page
- ✅ Teacher IDE with diff highlighting, dim mode, minimap
- ✅ Dark mode and multiple theme options
- ✅ Font-size and whitespace controls
- ✅ Timeline recording/editing + manual and suggested annotations
- ✅ Phase-3 API foundations for rendering, TTS, and voiceover auto-sync
- ✅ Student hint-only debug workflow (no code output)

### Still pending for later phases
- ❌ Real background render workers + FFmpeg composition
- ❌ Real TTS provider integration (OpenAI/ElevenLabs)
- ❌ Production auto-sync algorithm and quality scoring
- ❌ Hardened sandbox isolation for code execution
- ❌ Class enrollment/teacher-student data model
- ❌ JavaScript and GUI runtime support

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

Open:
- `http://localhost:8000/`
- `http://localhost:8000/login`
- `http://localhost:8000/teacher`
- `http://localhost:8000/student`

## Run with Docker Compose

```bash
docker compose up --build
```

Run this command from the repository root. It builds an image that copies the full project into `/app`, installs dependencies from `/app/requirements.txt`, and starts the API on port `8124`.

Open:
- `http://localhost:8124/`
- `http://localhost:8124/login`
- `http://localhost:8124/teacher`
- `http://localhost:8124/student`

## API

- `GET /health`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/execute`
- `POST /api/debug`
- `POST /api/recordings`
- `GET /api/recordings`
- `GET /api/recordings/{id}`
- `GET /api/recordings/{id}/suggest-annotations`
- `POST /api/render-jobs`
- `GET /api/render-jobs/{id}`
- `POST /api/voiceover/tts`
- `POST /api/voiceover/auto-sync`

## Tests

```bash
pytest
```
