# CodeStream - Phase 2 (UI Upgrade + Live Teaching)

This build upgrades the platform UI using **Bootstrap 5** and **Monaco Editor** (minimap-enabled), and aligns the implementation more closely with the product description.

## Implemented now

### Platform + access
- Web-based teacher/student pages
- Dedicated login page (`/login`) with register/login actions
- Role-based authentication endpoints

### Teacher IDE (Phase 2)
- Monaco-powered editor with minimap
- File switching
- Change emphasis modes:
  - highlight changed lines
  - dim unchanged lines
- Live recording of edit/file-switch/run events with timestamps
- Timeline tools:
  - remove selected event
  - trim long pauses
  - playback speed control (0.5x–4x)
- Manual annotations
- Suggested annotations endpoint (`/api/recordings/{id}/suggest-annotations`) as AI-assist placeholder
- Theme toggle (light/dark)
- Font size control
- Whitespace visibility toggle

### Student IDE
- Simplified Monaco editor UI
- Run code
- AI debug assistant endpoint with strict hint-only/no-code-output policy

### Backend
- Health endpoint
- Auth endpoints
- Python execution endpoint with timeout guard
- Debug endpoint
- Recordings create/list/get endpoints + suggestion endpoint

## Plan check vs provided product description

### Covered in this phase
- ✅ Login flow for teachers/students
- ✅ Teacher IDE optimized for coding demonstration
- ✅ Diff highlighting / dimming modes
- ✅ Live recording and timeline editing basics
- ✅ Manual annotation markers
- ✅ Minimap support
- ✅ Theme + font size + whitespace visibility controls
- ✅ Student debug guidance with no-code-output policy
- ✅ Python support baseline

### Not fully implemented yet (next phases)
- ❌ Production-grade auth/session management (refresh tokens, secure cookies)
- ❌ Secure containerized sandboxing with strict resource/network isolation
- ❌ Error/backspace removal as semantic post-processing (currently manual timeline editing)
- ❌ Automatic AI timestamping via external LLM API (currently heuristic placeholder)
- ❌ Video rendering pipeline + TTS + voiceover auto-sync
- ❌ Class enrollment workflows and role-scoped data models
- ❌ Multi-language execution support (JavaScript and more)
- ❌ GUI execution support (pygame/tkinter/p5.js)
- ❌ S3/Postgres production infrastructure

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

## Tests

```bash
pytest
```
