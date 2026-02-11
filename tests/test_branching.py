import uuid

import pytest

from backend.app.branching import resolve_branch_path
from backend.app.main import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "recordings.db"
    monkeypatch.setattr("backend.app.main.DB_PATH", db_path)
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def sample_recording():
    e1 = str(uuid.uuid4())
    e2 = str(uuid.uuid4())
    e3 = str(uuid.uuid4())
    return {
        "id": "rec-1",
        "active_branch": "main",
        "branch_parents": {"main": None, "debug": "main"},
        "branch_events": {"main": [e1, e2], "debug": [e3]},
        "events": [
            {"id": e1, "branch_name": "main", "parent_event_id": None, "intent": "setup"},
            {"id": e2, "branch_name": "main", "parent_event_id": e1, "intent": "loop intro"},
            {"id": e3, "branch_name": "debug", "parent_event_id": e2, "intent": "clarify bug"},
        ],
    }


def test_branch_path_selection_deterministic():
    recording = sample_recording()
    replay = resolve_branch_path(recording, branch_name="debug")

    assert [event["branch_name"] for event in replay] == ["main", "main", "debug"]
    assert [event["intent"] for event in replay] == ["setup", "loop intro", "clarify bug"]


def test_create_and_retrieve_branch_aware_recording(client):
    payload = sample_recording()

    response = client.post("/api/recordings", json=payload)
    assert response.status_code == 201

    list_response = client.get("/api/recordings?branch=debug")
    assert list_response.status_code == 200
    items = list_response.get_json()
    assert len(items) == 1
    assert items[0]["branches"] == ["debug", "main"]

    get_response = client.get("/api/recordings/rec-1?branch=debug")
    assert get_response.status_code == 200
    data = get_response.get_json()
    assert data["replay_branch"] == "debug"
    assert [event["branch_name"] for event in data["replay_events"]] == ["main", "main", "debug"]


def test_retrieve_unknown_branch_returns_400(client):
    payload = sample_recording()
    client.post("/api/recordings", json=payload)

    response = client.get("/api/recordings/rec-1?branch=unknown")
    assert response.status_code == 400
    assert "Unknown branch" in response.get_json()["error"]
