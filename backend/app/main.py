import json
import os
import re
from datetime import datetime
from typing import Dict, List

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import Mapped, Session, declarative_base, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool


Base = declarative_base()


class StudentDebugState(Base):
    __tablename__ = "student_debug_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    prior_errors: Mapped[str] = mapped_column(Text, default="[]")
    attempted_fixes: Mapped[str] = mapped_column(Text, default="[]")
    hint_level: Mapped[int] = mapped_column(Integer, default=1)
    repeated_error_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DebugRequest(BaseModel):
    student_id: str = Field(min_length=1)
    error: str = Field(min_length=1)
    attempted_fix: str | None = None


class HintStage(BaseModel):
    stage: str
    content: str


class DebugResponse(BaseModel):
    student_id: str
    hint_level: int
    repeated_error_count: int
    stages: List[HintStage]


def _create_engine(database_url: str):
    if database_url.startswith("sqlite") and ":memory:" in database_url:
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    if database_url.startswith("sqlite"):
        return create_engine(database_url, connect_args={"check_same_thread": False})
    return create_engine(database_url)


def is_over_specific_solution(text: str) -> bool:
    patterns = [
        r"\bcopy\s+paste\b",
        r"\bexact(?:ly)?\s+use\b",
        r"\breplace\s+line\s+\d+",
        r"\buse\s+this\s+code\b",
        r"\bthe\s+solution\s+is\b",
    ]
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in patterns)


def contains_code_snippet(text: str) -> bool:
    code_patterns = [
        r"```",
        r"\bdef\s+\w+\s*\(",
        r"\bclass\s+\w+",
        r"\breturn\s+.+",
        r"\bfor\s+\w+\s+in\s+",
        r";\s*$",
        r"\w+\s*=\s*.+",
    ]
    return any(re.search(pattern, text, flags=re.MULTILINE) for pattern in code_patterns)


def validate_hint_policy(stages: Dict[str, str]) -> None:
    for stage_name, text in stages.items():
        if contains_code_snippet(text) or is_over_specific_solution(text):
            raise HTTPException(
                status_code=400,
                detail=f"Policy violation in '{stage_name}': hints must stay conceptual and code-free.",
            )


def generate_hint_stages(error: str, hint_level: int, repeated_error_count: int) -> Dict[str, str]:
    depth_note = [
        "Start broad: identify where the failure starts.",
        "Narrow scope: inspect assumptions and intermediate values.",
        "Target likely root cause based on repeated failure pattern.",
        "Perform a focused diagnosis and compare expected versus actual behavior.",
    ][min(hint_level - 1, 3)]

    return {
        "diagnose": f"Interpret the error in plain language. {depth_note}",
        "probe_question": (
            "What single assumption would you verify first to test your current understanding "
            "of why this error happens?"
        ),
        "next_experiment": (
            "Run one small experiment that changes only one input or condition, then observe "
            "whether the same failure appears."
        ),
        "confidence_check": (
            f"Before moving on, explain why your experiment should affect the issue. "
            f"Current repeat count for this error: {repeated_error_count}."
        ),
    }


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(title="Code Stream Debug Coach")

    templates = Jinja2Templates(directory="backend/app/templates")
    app.mount("/static", StaticFiles(directory="backend/app/static"), name="static")

    db_url = database_url or os.getenv("DEBUG_STATE_DB_URL", "sqlite:///./debug_state.db")
    engine = _create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def get_or_create_state(db: Session, student_id: str) -> StudentDebugState:
        state = db.query(StudentDebugState).filter(StudentDebugState.student_id == student_id).first()
        if state:
            return state
        state = StudentDebugState(student_id=student_id, prior_errors="[]", attempted_fixes="[]")
        db.add(state)
        db.commit()
        db.refresh(state)
        return state

    @app.get("/", response_class=HTMLResponse)
    def student_page(request: Request):
        return templates.TemplateResponse("student.html", {"request": request})

    @app.post("/api/debug", response_model=DebugResponse)
    def debug_endpoint(payload: DebugRequest, db: Session = Depends(get_db)) -> DebugResponse:
        state = get_or_create_state(db, payload.student_id)

        prior_errors = json.loads(state.prior_errors or "[]")
        attempted_fixes = json.loads(state.attempted_fixes or "[]")

        is_repeat = bool(prior_errors and prior_errors[-1] == payload.error)
        state.repeated_error_count = state.repeated_error_count + 1 if is_repeat else 0
        state.hint_level = min(4, 1 + state.repeated_error_count)

        prior_errors.append(payload.error)
        state.prior_errors = json.dumps(prior_errors)

        if payload.attempted_fix:
            attempted_fixes.append(payload.attempted_fix)
            state.attempted_fixes = json.dumps(attempted_fixes)

        stages_dict = generate_hint_stages(payload.error, state.hint_level, state.repeated_error_count)
        validate_hint_policy(stages_dict)

        state.updated_at = datetime.utcnow()
        db.add(state)
        db.commit()

        ordered_names = ["diagnose", "probe_question", "next_experiment", "confidence_check"]
        ordered_stages = [HintStage(stage=name, content=stages_dict[name]) for name in ordered_names]

        return DebugResponse(
            student_id=payload.student_id,
            hint_level=state.hint_level,
            repeated_error_count=state.repeated_error_count,
            stages=ordered_stages,
        )

    return app


app = create_app()
