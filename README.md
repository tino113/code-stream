# CodeStream - Phase 2 (Live Teaching Features)

This repository now includes a Phase 2 implementation on top of Phase 1.

## Implemented

### Phase 1 foundation
- FastAPI backend with auth endpoints
- Teacher and Student IDE pages
- Python code execution endpoint
- AI debug-hint endpoint with no-code-output policy

### Phase 2 live teaching features
- Change highlighting system with two modes:
  - highlight changed lines in amber/green
  - dim unchanged lines
- Live recording system for teacher IDE:
  - records edit events
  - records file navigation events
  - records run events with timestamps
- Timeline editing:
  - remove selected events
  - trim pauses longer than 3s
  - playback speed controls (0.5x to 4x)
- Manual timestamp + annotation markers
- Recording persistence API (`/api/recordings`)

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

Open:
- `http://localhost:8000/`
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

## Test

```bash
pytest
```
