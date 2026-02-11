from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def _event(
    student_id: str,
    segment: str,
    marker: str,
    event_type: str,
    seconds: int,
    concept_tags: list[str],
    hint_stage: str = "none",
    misconception_cluster: str | None = None,
):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return {
        "student_id": student_id,
        "lesson_id": "lesson-demo",
        "lesson_segment_id": segment,
        "timeline_marker_id": marker,
        "timestamp": (base + timedelta(seconds=seconds)).isoformat(),
        "event_type": event_type,
        "concept_tags": concept_tags,
        "hint_stage": hint_stage,
        "misconception_cluster": misconception_cluster,
    }


def setup_function() -> None:
    client.delete("/analytics/events")


def test_confusion_hotspots_aggregate_by_concept_and_segment() -> None:
    payload = {
        "events": [
            _event("s1", "seg-1", "m1", "error_syntax", 0, ["loops"], misconception_cluster="off-by-one"),
            _event("s1", "seg-1", "m1", "hint_opened", 5, ["loops"], hint_stage="level_1"),
            _event("s1", "seg-1", "m1", "checkpoint_retry", 6, ["loops"]),
            _event("s1", "seg-1", "m1", "run_success", 10, ["loops"]),
            _event("s2", "seg-2", "m2", "run_success", 1, ["arrays"]),
        ]
    }
    client.post("/analytics/events", json=payload)

    response = client.get("/analytics/confusion-hotspots", params={"lesson_id": "lesson-demo"})

    assert response.status_code == 200
    body = response.json()
    assert body["hotspots"][0]["concept"] == "loops"
    assert body["hotspots"][0]["lesson_segment_id"] == "seg-1"
    assert body["hotspots"][0]["confusion_score"] == 3.0
    assert body["hotspots"][0]["timeline_marker"]["id"] == "m1"


def test_teacher_trends_compute_time_hint_ratio_and_misconception_repeats() -> None:
    payload = {
        "events": [
            _event("s1", "seg-1", "m1", "error_logic", 0, ["conditionals"], misconception_cluster="branch-order"),
            _event("s1", "seg-1", "m1", "hint_applied", 30, ["conditionals"], hint_stage="level_2"),
            _event("s1", "seg-1", "m1", "run_success", 90, ["conditionals"]),
            _event("s2", "seg-1", "m1", "error_runtime", 0, ["conditionals"], misconception_cluster="branch-order"),
            _event("s2", "seg-1", "m1", "run_success", 45, ["conditionals"]),
        ]
    }
    client.post("/analytics/events", json=payload)

    response = client.get("/analytics/teacher-trends", params={"lesson_id": "lesson-demo"})

    assert response.status_code == 200
    body = response.json()
    trends = body["trend_lines"]
    assert trends["time_to_first_success"][0] == {"lesson_segment_id": "seg-1", "seconds": 67.5}
    assert trends["hint_dependency_ratio"][0] == {"lesson_segment_id": "seg-1", "ratio": 0.5}
    assert trends["repeated_misconception_clusters"][0] == {"cluster": "branch-order", "count": 2}
    assert body["timeline_markers"][0]["marker_id"] == "m1"
