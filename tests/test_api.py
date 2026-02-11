from pathlib import Path

from backend.app.main import App, RecordingStore


def _sample_scene():
    return {
        "focus_line_range": [3, 10],
        "zoom_level": 1.5,
        "spotlight_blocks": ["loop", "return"],
        "transition_type": "fade",
    }


def test_scene_persistence_per_recording(tmp_path: Path):
    app = App(store=RecordingStore(db_path=tmp_path / "recordings.db"))

    create = app.handle(
        "POST",
        "/api/recordings",
        {
            "events": [{"t": 1, "type": "insert", "line": 3}],
            "scenes": [_sample_scene()],
        },
    )

    assert create.status == 201
    recording_id = create.body["id"]

    fetched = app.handle("GET", f"/api/recordings/{recording_id}")
    assert fetched.status == 200
    assert fetched.body["scenes"] == [_sample_scene()]


def test_render_jobs_accept_scene_metadata_and_return_render_plan(tmp_path: Path):
    app = App(store=RecordingStore(db_path=tmp_path / "recordings.db"))

    created = app.handle("POST", "/api/recordings", {"events": [{"t": 1}], "scenes": []})
    recording_id = created.body["id"]

    scene_metadata = [
        {
            "focus_line_range": [1, 5],
            "zoom_level": 2.0,
            "spotlight_blocks": ["init"],
            "transition_type": "cut",
        }
    ]
    render = app.handle(
        "POST",
        "/api/render-jobs",
        {"recording_id": recording_id, "scene_metadata": scene_metadata},
    )

    assert render.status == 201
    assert render.body["render_plan"]["scene_count"] == 1
    assert render.body["render_plan"]["timeline"][0]["transition_type"] == "cut"


def test_render_jobs_reject_invalid_scene_payload(tmp_path: Path):
    app = App(store=RecordingStore(db_path=tmp_path / "recordings.db"))
    created = app.handle("POST", "/api/recordings", {"events": [{"t": 1}]})

    invalid_scene_metadata = [
        {
            "focus_line_range": [1],
            "zoom_level": 0,
            "spotlight_blocks": "loop",
            "transition_type": "jump",
        }
    ]

    render = app.handle(
        "POST",
        "/api/render-jobs",
        {"recording_id": created.body["id"], "scene_metadata": invalid_scene_metadata},
    )

    assert render.status == 400
    assert "focus_line_range" in render.body["error"]
