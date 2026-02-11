from datetime import timedelta

from backend.app.main import (
    REPEATED_TRACEBACK_STUCK,
    SUCCESS_GAP_STUCK,
    StudentState,
    app,
    store,
    stuck_indicators,
    stuck_risk_score,
    utcnow,
)


def setup_function() -> None:
    store.classrooms.clear()


def _create_session(client, classroom_id="class-a", session_id="session-a"):
    response = client.post(
        f"/api/classrooms/{classroom_id}/sessions",
        json={"session_id": session_id},
    )
    assert response.status_code == 201
    return session_id


def test_stuck_heuristics_thresholds():
    now = utcnow()
    student = StudentState(student_id="s1")
    student.last_successful_run_at = now - SUCCESS_GAP_STUCK
    student.last_error_at = now - timedelta(minutes=1)
    student.last_edit_at = now - timedelta(minutes=2)
    student.same_traceback_streak = REPEATED_TRACEBACK_STUCK

    indicators = stuck_indicators(student, now=now)

    assert indicators["stale_success"] is True
    assert indicators["repeated_same_traceback"] is True
    assert indicators["no_edits_after_error"] is True
    assert stuck_risk_score(student, now=now) == 100


def test_dashboard_summary_outputs_sorted_risk_and_counts():
    client = app.test_client()
    session_id = _create_session(client)

    # High-risk student: stale success + same traceback x3 + no edits after error.
    base_time = utcnow()
    client.post(
        f"/api/sessions/{session_id}/heartbeat",
        json={
            "student_id": "high",
            "display_name": "High Risk",
            "event_type": "run_success",
            "timestamp": (base_time - timedelta(minutes=20)).isoformat(),
        },
    )
    for _ in range(3):
        client.post(
            f"/api/sessions/{session_id}/heartbeat",
            json={
                "student_id": "high",
                "event_type": "run_error",
                "timestamp": (base_time - timedelta(minutes=1)).isoformat(),
                "payload": {"traceback": "ValueError: x"},
            },
        )

    # Low-risk student: recent success and a fresh edit after error.
    client.post(
        f"/api/sessions/{session_id}/heartbeat",
        json={
            "student_id": "low",
            "display_name": "Low Risk",
            "event_type": "run_success",
            "timestamp": utcnow().isoformat(),
        },
    )
    client.post(
        f"/api/sessions/{session_id}/heartbeat",
        json={
            "student_id": "low",
            "event_type": "run_error",
            "timestamp": utcnow().isoformat(),
            "payload": {"traceback": "TypeError: y"},
        },
    )
    client.post(
        f"/api/sessions/{session_id}/heartbeat",
        json={
            "student_id": "low",
            "event_type": "edit",
            "timestamp": utcnow().isoformat(),
        },
    )

    response = client.get(f"/api/sessions/{session_id}/dashboard_summary")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["student_count"] == 2
    assert payload["high_risk_count"] == 1
    assert [student["student_id"] for student in payload["students"]] == ["high", "low"]

    high = payload["students"][0]
    assert high["risk_score"] >= 60
    assert high["indicators"]["repeated_same_traceback"] is True


def test_intervention_metadata_request_defaults_to_no_code():
    client = app.test_client()
    session_id = _create_session(client)
    client.post(
        f"/api/sessions/{session_id}/heartbeat",
        json={"student_id": "student-a", "event_type": "debug", "timestamp": utcnow().isoformat()},
    )

    response = client.post(
        f"/api/sessions/{session_id}/students/student-a/interventions/request_snippet_metadata",
        json={"reason": "need context"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    recent = payload["student"]["recent_interventions"][-1]
    assert recent["action"] == "request_snippet_metadata"
    assert recent["payload"]["include_code"] is False
    assert recent["payload"]["reason"] == "need context"
