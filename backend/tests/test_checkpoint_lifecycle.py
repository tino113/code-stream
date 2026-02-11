from backend.app import create_app


def test_checkpoint_lifecycle_assigned_attempted_passed_unlocked():
    app = create_app()
    client = app.test_client()

    annotation_resp = client.post(
        "/api/teacher/annotations",
        json={"timestamp": 42.0, "note": "Checkpoint note"},
    )
    annotation = annotation_resp.get_json()

    checkpoint_resp = client.post(
        "/api/teacher/checkpoints",
        json={
            "annotation_id": annotation["id"],
            "prompt": "What concept applies?",
            "expected_concept_tags": ["recursion"],
            "unlock_condition": "pass_checkpoint",
        },
    )
    checkpoint = checkpoint_resp.get_json()

    student_id = "student-1"

    playback_resp = client.get(f"/api/student/{student_id}/playback")
    state = playback_resp.get_json()["checkpoint_states"][checkpoint["id"]]
    assert state["status"] == "assigned"

    attempt_resp = client.post(
        f"/api/student/{student_id}/checkpoints/{checkpoint['id']}/state",
        json={"action": "attempt", "used_hint": True, "runtime_success": False},
    )
    assert attempt_resp.get_json()["status"] == "attempted"

    pass_resp = client.post(
        f"/api/student/{student_id}/checkpoints/{checkpoint['id']}/state",
        json={"action": "pass"},
    )
    assert pass_resp.get_json()["status"] == "passed"

    unlock_resp = client.post(
        f"/api/student/{student_id}/checkpoints/{checkpoint['id']}/state",
        json={"action": "unlock"},
    )
    assert unlock_resp.get_json()["status"] == "unlocked"


def test_rubric_scoring_uses_behavior_signals():
    app = create_app()
    client = app.test_client()

    annotation = client.post(
        "/api/teacher/annotations", json={"timestamp": 50.0, "note": "another"}
    ).get_json()
    checkpoint = client.post(
        "/api/teacher/checkpoints",
        json={
            "annotation_id": annotation["id"],
            "prompt": "Analyze complexity",
            "expected_concept_tags": ["big-o"],
            "unlock_condition": "pass_checkpoint",
        },
    ).get_json()

    student_id = "student-2"
    client.post(
        f"/api/student/{student_id}/checkpoints/{checkpoint['id']}/state",
        json={"action": "attempt", "used_hint": True, "runtime_success": False},
    )
    client.post(
        f"/api/student/{student_id}/checkpoints/{checkpoint['id']}/state",
        json={"action": "attempt", "used_hint": False, "runtime_success": True},
    )

    rubric = client.get(
        f"/api/student/{student_id}/checkpoints/{checkpoint['id']}/rubric"
    ).get_json()

    assert rubric["signals"]["attempt_count"] == 2
    assert rubric["signals"]["hint_count"] == 1
    assert rubric["signals"]["runtime_success_count"] == 1
    assert rubric["rubric"]["total"] > 0
