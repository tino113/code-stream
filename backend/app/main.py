"""Minimal recording API with scene-layer metadata support."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from wsgiref.util import setup_testing_defaults

DB_PATH = Path(__file__).with_name("recordings.db")


SCENE_REQUIRED_KEYS = {
    "focus_line_range",
    "zoom_level",
    "spotlight_blocks",
    "transition_type",
}
VALID_TRANSITIONS = {"cut", "fade", "slide", "wipe"}


@dataclass
class Response:
    status: int
    body: dict[str, Any]


class RecordingStore:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS recordings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    events_json TEXT NOT NULL,
                    scenes_json TEXT NOT NULL DEFAULT '[]'
                )
                """
            )

    def create_recording(self, events: list[dict[str, Any]], scenes: list[dict[str, Any]]) -> dict[str, Any]:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO recordings (events_json, scenes_json) VALUES (?, ?)",
                (json.dumps(events), json.dumps(scenes)),
            )
            new_id = cursor.lastrowid
        return self.get_recording(new_id)

    def get_recording(self, recording_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, events_json, scenes_json FROM recordings WHERE id = ?",
                (recording_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"recording {recording_id} not found")

        return {
            "id": row["id"],
            "events": json.loads(row["events_json"]),
            "scenes": json.loads(row["scenes_json"]),
        }


def _validate_scene(scene: dict[str, Any]) -> str | None:
    missing = SCENE_REQUIRED_KEYS - set(scene)
    if missing:
        return f"Missing scene keys: {', '.join(sorted(missing))}"

    focus = scene["focus_line_range"]
    if not isinstance(focus, list) or len(focus) != 2 or not all(isinstance(n, int) for n in focus):
        return "focus_line_range must be a list of two integers"

    zoom = scene["zoom_level"]
    if not isinstance(zoom, (int, float)) or zoom <= 0:
        return "zoom_level must be a positive number"

    spotlight = scene["spotlight_blocks"]
    if not isinstance(spotlight, list) or not all(isinstance(s, str) for s in spotlight):
        return "spotlight_blocks must be a list of block ids"

    transition = scene["transition_type"]
    if transition not in VALID_TRANSITIONS:
        return f"transition_type must be one of: {', '.join(sorted(VALID_TRANSITIONS))}"

    return None


def _validate_scenes(scenes: Any) -> str | None:
    if scenes is None:
        return None
    if not isinstance(scenes, list):
        return "scenes must be a list"
    for idx, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            return f"scene at index {idx} must be an object"
        err = _validate_scene(scene)
        if err:
            return f"scene {idx}: {err}"
    return None


def build_render_plan(recording: dict[str, Any], scene_metadata: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    scenes = scene_metadata if scene_metadata is not None else recording.get("scenes", [])
    return {
        "recording_id": recording["id"],
        "event_count": len(recording.get("events", [])),
        "scene_count": len(scenes),
        "timeline": [
            {
                "scene_index": idx,
                "focus_line_range": scene["focus_line_range"],
                "zoom_level": scene["zoom_level"],
                "spotlight_blocks": scene["spotlight_blocks"],
                "transition_type": scene["transition_type"],
            }
            for idx, scene in enumerate(scenes)
        ],
    }


class App:
    def __init__(self, store: RecordingStore | None = None):
        self.store = store or RecordingStore()

    def handle(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Response:
        payload = payload or {}

        if method == "POST" and path == "/api/recordings":
            scenes = payload.get("scenes", [])
            err = _validate_scenes(scenes)
            if err:
                return Response(400, {"error": err})

            events = payload.get("events", [])
            if not isinstance(events, list):
                return Response(400, {"error": "events must be a list"})

            recording = self.store.create_recording(events=events, scenes=scenes)
            return Response(201, recording)

        if method == "POST" and path == "/api/render-jobs":
            recording_id = payload.get("recording_id")
            if not isinstance(recording_id, int):
                return Response(400, {"error": "recording_id must be an integer"})

            try:
                recording = self.store.get_recording(recording_id)
            except KeyError:
                return Response(404, {"error": "recording not found"})

            scene_metadata = payload.get("scene_metadata")
            err = _validate_scenes(scene_metadata)
            if err:
                return Response(400, {"error": err})

            render_plan = build_render_plan(recording, scene_metadata)
            return Response(
                201,
                {
                    "render_job": {
                        "id": f"job-{recording_id}",
                        "status": "queued",
                    },
                    "render_plan": render_plan,
                },
            )

        if method == "GET" and path.startswith("/api/recordings/"):
            maybe_id = path.rsplit("/", 1)[-1]
            try:
                recording_id = int(maybe_id)
                recording = self.store.get_recording(recording_id)
                return Response(200, recording)
            except (ValueError, KeyError):
                return Response(404, {"error": "recording not found"})

        return Response(404, {"error": "not found"})


# Optional WSGI adapter for local use.
def create_wsgi_app(app: App | None = None):
    application = app or App()

    def _wsgi(environ, start_response):
        setup_testing_defaults(environ)
        method = environ["REQUEST_METHOD"]
        path = environ.get("PATH_INFO", "/")
        raw_body = environ["wsgi.input"].read(int(environ.get("CONTENT_LENGTH") or 0) or 0)
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        response = application.handle(method, path, payload)

        status_text = f"{response.status} OK"
        start_response(status_text, [("Content-Type", "application/json")])
        return [json.dumps(response.body).encode("utf-8")]

    return _wsgi


if __name__ == "__main__":
    from wsgiref.simple_server import make_server

    wsgi_app = create_wsgi_app()
    with make_server("127.0.0.1", 8080, wsgi_app) as server:
        print("Serving on http://127.0.0.1:8080")
        server.serve_forever()
