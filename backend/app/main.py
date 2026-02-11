from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import re
import subprocess
import tempfile
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, Integer, String, Text, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = "sqlite:///./codestream.db"
SECRET_KEY = "dev-secret-change-me"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)
    active = Column(Boolean, default=True)


class Recording(Base):
    __tablename__ = "recordings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    created_by = Column(String, nullable=False)
    events_json = Column(Text, nullable=False)
    annotations_json = Column(Text, nullable=False, default="[]")


class RenderJob(Base):
    __tablename__ = "render_jobs"

    id = Column(Integer, primary_key=True, index=True)
    recording_id = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="queued")
    format = Column(String, nullable=False, default="mp4")
    output_url = Column(String, nullable=False, default="")


Base.metadata.create_all(bind=engine)


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    role: str = Field(pattern="^(teacher|student)$")


class LoginRequest(BaseModel):
    email: str
    password: str


class ExecuteRequest(BaseModel):
    code: str = Field(max_length=10000)


class DebugRequest(BaseModel):
    code: str = Field(max_length=10000)
    error_message: str = Field(max_length=4000)


class RecordingPayload(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    created_by: str = Field(min_length=3, max_length=120)
    events: list[dict]
    annotations: list[dict] = []


class RenderPayload(BaseModel):
    recording_id: int
    format: str = Field(default="mp4", pattern="^(mp4|webm)$")


class TtsPayload(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    voice: str = Field(default="alloy", max_length=60)


class AutoSyncPayload(BaseModel):
    recording_id: int
    transcript_chunks: list[dict]


app = FastAPI(title="CodeStream API", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def sanitize_debug_reply(text: str) -> str:
    text = re.sub(r"```.*?```", "[code removed]", text, flags=re.S)
    lines = [line for line in text.splitlines() if not line.strip().startswith(("def ", "class ", "import "))]
    return "\n".join(lines).strip()


@app.get("/health")
def health_check():
    return {"status": "ok", "phase": 3, "ui": "bootstrap+monaco"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/teacher", response_class=HTMLResponse)
def teacher(request: Request):
    return templates.TemplateResponse("teacher.html", {"request": request})


@app.get("/student", response_class=HTMLResponse)
def student(request: Request):
    return templates.TemplateResponse("student.html", {"request": request})


@app.post("/api/auth/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    user = User(email=payload.email.lower(), hashed_password=hash_password(payload.password), role=payload.role)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered")
    return {"message": "User created"}


@app.post("/api/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": user.email, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "role": user.role}


@app.post("/api/execute")
def execute_python(payload: ExecuteRequest):
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            program = Path(temp_dir) / "main.py"
            program.write_text(payload.code)
            proc = subprocess.run(
                ["python3", str(program)],
                capture_output=True,
                text=True,
                timeout=2,
                cwd=temp_dir,
            )
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Execution timed out after 2 seconds.", "exit_code": -1}

    output = (proc.stdout or "")[:4000]
    error = (proc.stderr or "")[:4000]
    return {"stdout": output, "stderr": error, "exit_code": proc.returncode}


@app.post("/api/debug")
def debug_agent(payload: DebugRequest):
    error = payload.error_message.strip()

    response = (
        "I can help you debug without giving the final code.\n"
        f"1) Error meaning: {error.splitlines()[0] if error else 'No error text supplied.'}\n"
        "2) Check the traceback line, then inspect variable naming and indentation nearby.\n"
        "3) Add small print() checks before the failing line to inspect values/types.\n"
        "4) Re-run after one change at a time and compare outputs."
    )

    return {"guidance": sanitize_debug_reply(response), "policy": "no_code_output"}


@app.post("/api/recordings")
def create_recording(payload: RecordingPayload, db: Session = Depends(get_db)):
    record = Recording(
        title=payload.title,
        created_by=payload.created_by,
        events_json=json.dumps(payload.events),
        annotations_json=json.dumps(payload.annotations),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"id": record.id, "title": record.title, "created_by": record.created_by}


@app.get("/api/recordings")
def list_recordings(db: Session = Depends(get_db)):
    records = db.query(Recording).order_by(Recording.id.desc()).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "created_by": r.created_by,
            "event_count": len(json.loads(r.events_json)),
            "annotation_count": len(json.loads(r.annotations_json)),
        }
        for r in records
    ]


@app.get("/api/recordings/{recording_id}")
def get_recording(recording_id: int, db: Session = Depends(get_db)):
    rec = db.query(Recording).filter(Recording.id == recording_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")

    return {
        "id": rec.id,
        "title": rec.title,
        "created_by": rec.created_by,
        "events": json.loads(rec.events_json),
        "annotations": json.loads(rec.annotations_json),
    }


@app.get("/api/recordings/{recording_id}/suggest-annotations")
def suggest_annotations(recording_id: int, db: Session = Depends(get_db)):
    rec = db.query(Recording).filter(Recording.id == recording_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")

    events = json.loads(rec.events_json)
    suggestions = []
    for event in events:
        if event.get("type") in {"run", "file_switch"}:
            suggestions.append(
                {
                    "t": event.get("t", 0),
                    "text": f"Checkpoint: {event.get('type')} in {event.get('file', 'current file')}",
                    "file": event.get("file", "main.py"),
                }
            )

    return {"recording_id": recording_id, "suggestions": suggestions[:10], "source": "heuristic_ai_placeholder"}


@app.post("/api/render-jobs")
def create_render_job(payload: RenderPayload, db: Session = Depends(get_db)):
    recording = db.query(Recording).filter(Recording.id == payload.recording_id).first()
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")

    job = RenderJob(recording_id=payload.recording_id, status="queued", format=payload.format)
    db.add(job)
    db.commit()
    db.refresh(job)

    # phase-3 lightweight pipeline placeholder: mark completed synchronously
    job.status = "completed"
    job.output_url = f"https://cdn.codestream.local/renders/{job.id}.{job.format}"
    db.commit()
    db.refresh(job)

    return {"job_id": job.id, "status": job.status, "output_url": job.output_url}


@app.get("/api/render-jobs/{job_id}")
def get_render_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(RenderJob).filter(RenderJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Render job not found")
    return {
        "job_id": job.id,
        "recording_id": job.recording_id,
        "status": job.status,
        "format": job.format,
        "output_url": job.output_url,
    }


@app.post("/api/voiceover/tts")
def synthesize_tts(payload: TtsPayload):
    # phase-3 API contract placeholder to integrate real providers later
    audio_id = str(uuid4())
    return {
        "audio_id": audio_id,
        "voice": payload.voice,
        "duration_seconds": max(2, len(payload.text.split()) // 2),
        "audio_url": f"https://cdn.codestream.local/voice/{audio_id}.mp3",
        "provider": "placeholder_tts",
    }


@app.post("/api/voiceover/auto-sync")
def auto_sync_voiceover(payload: AutoSyncPayload, db: Session = Depends(get_db)):
    rec = db.query(Recording).filter(Recording.id == payload.recording_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")

    events = json.loads(rec.events_json)
    run_points = [e for e in events if e.get("type") in {"run", "annotation", "file_switch"}]
    if not run_points:
        run_points = [{"t": 0, "type": "start", "file": "main.py"}]

    chunks = payload.transcript_chunks or [{"text": "Intro"}]
    plan = []
    for i, chunk in enumerate(chunks):
        anchor = run_points[min(i, len(run_points) - 1)]
        plan.append(
            {
                "chunk_index": i,
                "text": chunk.get("text", ""),
                "start_ms": anchor.get("t", 0),
                "speed": chunk.get("target_speed", 1.0),
                "anchor_type": anchor.get("type", "start"),
            }
        )

    return {"recording_id": payload.recording_id, "segments": plan, "strategy": "event-anchor-alignment-v1"}
