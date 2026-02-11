from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from flask import Flask, jsonify, render_template, request

app = Flask(__name__, template_folder="templates")


@dataclass
class Event:
    event_type: str
    timestamp: datetime
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class Intervention:
    action: str
    created_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class StudentState:
    student_id: str
    display_name: str | None = None
    events: list[Event] = field(default_factory=list)
    interventions: list[Intervention] = field(default_factory=list)
    last_successful_run_at: datetime | None = None
    last_error_at: datetime | None = None
    last_edit_at: datetime | None = None
    last_traceback: str | None = None
    same_traceback_streak: int = 0


@dataclass
class Session:
    session_id: str
    classroom_id: str
    created_at: datetime
    students: dict[str, StudentState] = field(default_factory=dict)


@dataclass
class Classroom:
    classroom_id: str
    name: str | None = None
    sessions: dict[str, Session] = field(default_factory=dict)


class Store:
    def __init__(self) -> None:
        self.classrooms: dict[str, Classroom] = {}


store = Store()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(value: str | None) -> datetime:
    if not value:
        return utcnow()
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def get_session(session_id: str) -> Session:
    for classroom in store.classrooms.values():
        if session_id in classroom.sessions:
            return classroom.sessions[session_id]
    raise KeyError(f"Unknown session {session_id}")


def get_or_create_student(session: Session, student_id: str, display_name: str | None) -> StudentState:
    student = session.students.get(student_id)
    if not student:
        student = StudentState(student_id=student_id, display_name=display_name)
        session.students[student_id] = student
    elif display_name:
        student.display_name = display_name
    return student


def apply_event(student: StudentState, event: Event) -> None:
    student.events.append(event)
    if event.event_type == "run_success":
        student.last_successful_run_at = event.timestamp
        student.last_traceback = None
        student.same_traceback_streak = 0
    elif event.event_type == "run_error":
        student.last_error_at = event.timestamp
        traceback_text = str(event.payload.get("traceback", ""))
        if traceback_text and traceback_text == student.last_traceback:
            student.same_traceback_streak += 1
        else:
            student.same_traceback_streak = 1 if traceback_text else 0
        student.last_traceback = traceback_text or None
    elif event.event_type == "edit":
        student.last_edit_at = event.timestamp
    elif event.event_type == "debug":
        # debug interactions are currently recorded for timeline visibility
        pass


SUCCESS_GAP_STUCK = timedelta(minutes=10)
REPEATED_TRACEBACK_STUCK = 3


def stuck_indicators(student: StudentState, now: datetime | None = None) -> dict[str, Any]:
    now = now or utcnow()
    if student.last_successful_run_at:
        success_gap = now - student.last_successful_run_at
    else:
        success_gap = timedelta.max

    no_edits_after_error = bool(
        student.last_error_at
        and (student.last_edit_at is None or student.last_edit_at < student.last_error_at)
    )

    indicators = {
        "seconds_since_successful_run": int(success_gap.total_seconds()) if success_gap != timedelta.max else None,
        "stale_success": success_gap >= SUCCESS_GAP_STUCK,
        "repeated_same_traceback": student.same_traceback_streak >= REPEATED_TRACEBACK_STUCK,
        "no_edits_after_error": no_edits_after_error,
        "same_traceback_streak": student.same_traceback_streak,
    }
    return indicators


def stuck_risk_score(student: StudentState, now: datetime | None = None) -> int:
    indicators = stuck_indicators(student, now=now)
    score = 0
    if indicators["stale_success"]:
        score += 40
    if indicators["repeated_same_traceback"]:
        score += 35
    if indicators["no_edits_after_error"]:
        score += 25
    return min(score, 100)


def student_summary(student: StudentState, now: datetime | None = None) -> dict[str, Any]:
    indicators = stuck_indicators(student, now=now)
    return {
        "student_id": student.student_id,
        "display_name": student.display_name or student.student_id,
        "risk_score": stuck_risk_score(student, now=now),
        "indicators": indicators,
        "last_successful_run_at": student.last_successful_run_at.isoformat() if student.last_successful_run_at else None,
        "last_error_at": student.last_error_at.isoformat() if student.last_error_at else None,
        "last_edit_at": student.last_edit_at.isoformat() if student.last_edit_at else None,
        "recent_interventions": [
            {
                "action": item.action,
                "created_at": item.created_at.isoformat(),
                "payload": item.payload,
            }
            for item in student.interventions[-3:]
        ],
    }


@app.post("/api/classrooms/<classroom_id>/sessions")
def create_session(classroom_id: str):
    payload = request.get_json(silent=True) or {}
    classroom = store.classrooms.get(classroom_id)
    if not classroom:
        classroom = Classroom(classroom_id=classroom_id, name=payload.get("classroom_name"))
        store.classrooms[classroom_id] = classroom

    session_id = payload.get("session_id") or str(uuid4())
    session = Session(session_id=session_id, classroom_id=classroom_id, created_at=utcnow())
    classroom.sessions[session_id] = session
    return jsonify({"session_id": session_id, "classroom_id": classroom_id}), 201


@app.post("/api/sessions/<session_id>/heartbeat")
def ingest_heartbeat(session_id: str):
    payload = request.get_json(force=True)
    event_type = payload.get("event_type")
    if event_type not in {"run_success", "run_error", "edit", "debug"}:
        return jsonify({"error": "Unsupported event_type"}), 400

    student_id = payload.get("student_id")
    if not student_id:
        return jsonify({"error": "student_id is required"}), 400

    try:
        session = get_session(session_id)
    except KeyError:
        return jsonify({"error": "Unknown session"}), 404

    student = get_or_create_student(session, student_id, payload.get("display_name"))
    event = Event(
        event_type=event_type,
        timestamp=parse_ts(payload.get("timestamp")),
        payload=payload.get("payload") or {},
    )
    apply_event(student, event)

    return jsonify(
        {
            "session_id": session_id,
            "student": student_summary(student),
        }
    )


@app.get("/api/sessions/<session_id>/dashboard_summary")
def dashboard_summary(session_id: str):
    try:
        session = get_session(session_id)
    except KeyError:
        return jsonify({"error": "Unknown session"}), 404

    now = utcnow()
    summaries = [student_summary(student, now=now) for student in session.students.values()]
    summaries.sort(key=lambda item: item["risk_score"], reverse=True)
    return jsonify(
        {
            "session_id": session_id,
            "classroom_id": session.classroom_id,
            "student_count": len(summaries),
            "students": summaries,
            "high_risk_count": sum(1 for s in summaries if s["risk_score"] >= 60),
        }
    )


@app.post("/api/sessions/<session_id>/students/<student_id>/interventions/<action>")
def apply_intervention(session_id: str, student_id: str, action: str):
    if action not in {"hint", "checkpoint", "request_snippet_metadata"}:
        return jsonify({"error": "Unknown intervention"}), 400

    try:
        session = get_session(session_id)
    except KeyError:
        return jsonify({"error": "Unknown session"}), 404

    student = get_or_create_student(session, student_id, None)
    payload = request.get_json(silent=True) or {}

    intervention_payload = dict(payload)
    if action == "request_snippet_metadata":
        intervention_payload.setdefault("include_code", False)

    intervention = Intervention(action=action, created_at=utcnow(), payload=intervention_payload)
    student.interventions.append(intervention)

    return jsonify({"ok": True, "student": student_summary(student)})


@app.get("/teacher/<session_id>")
def teacher_view(session_id: str):
    try:
        session = get_session(session_id)
    except KeyError:
        return "Unknown session", 404

    summaries = [student_summary(student) for student in session.students.values()]
    summaries.sort(key=lambda item: item["risk_score"], reverse=True)
    return render_template("teacher.html", session=session, students=summaries)


if __name__ == "__main__":
    app.run(debug=True)
