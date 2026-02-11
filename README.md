# CodeStream - Phase 1 Foundation

This repository contains a Phase 1 implementation of CodeStream with:

- FastAPI backend with auth endpoints
- Teacher and Student IDE pages
- Python code execution endpoint
- AI debug-hint endpoint with no-code-output policy

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

## Test

```bash
pytest
```
