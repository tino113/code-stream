from fastapi.testclient import TestClient

from backend.app import main


def build_client():
    app = main.create_app("sqlite:///:memory:")
    return TestClient(app)


def test_stage_sequencing_returns_guided_stages():
    client = build_client()

    response = client.post(
        "/api/debug",
        json={"student_id": "s-1", "error": "IndexError", "attempted_fix": "checked list length"},
    )

    assert response.status_code == 200
    data = response.json()
    assert [stage["stage"] for stage in data["stages"]] == [
        "diagnose",
        "probe_question",
        "next_experiment",
        "confidence_check",
    ]


def test_policy_rejects_direct_code_like_hints(monkeypatch):
    client = build_client()

    def violating_generator(error: str, hint_level: int, repeated_error_count: int):
        return {
            "diagnose": "Use this code: def fix_bug(): return 1",
            "probe_question": "Why?",
            "next_experiment": "Try something",
            "confidence_check": "Explain confidence",
        }

    monkeypatch.setattr(main, "generate_hint_stages", violating_generator)

    response = client.post("/api/debug", json={"student_id": "s-2", "error": "TypeError"})

    assert response.status_code == 400
    assert "Policy violation" in response.json()["detail"]


def test_repeated_error_escalates_hint_level():
    client = build_client()

    first = client.post("/api/debug", json={"student_id": "s-3", "error": "ValueError"})
    second = client.post("/api/debug", json={"student_id": "s-3", "error": "ValueError"})
    third = client.post("/api/debug", json={"student_id": "s-3", "error": "ValueError"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 200

    assert first.json()["hint_level"] == 1
    assert second.json()["hint_level"] == 2
    assert third.json()["hint_level"] == 3
    assert third.json()["repeated_error_count"] == 2
