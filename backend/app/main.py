from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, render_template, request

from .branching import materialize_branch_events, resolve_branch_path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "backend" / "recordings.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recordings (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def normalize_recording(payload: Dict[str, Any]) -> Dict[str, Any]:
    events = payload.get("events", [])
    for event in events:
        event.setdefault("id", str(uuid.uuid4()))
        event.setdefault("branch_name", "main")
        event.setdefault("parent_event_id", None)
        event.setdefault("intent", "")

    payload.setdefault("branch_events", materialize_branch_events(events))
    payload.setdefault("branch_parents", {"main": None})
    payload.setdefault("active_branch", payload.get("active_branch", "main"))
    return payload


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    init_db()

    @app.get("/")
    def teacher_view():
        return render_template("teacher.html")

    @app.post("/api/recordings")
    def create_recording():
        payload = normalize_recording(request.get_json(force=True) or {})
        recording_id = payload.get("id") or str(uuid.uuid4())
        payload["id"] = recording_id

        conn = _connect()
        conn.execute(
            "INSERT OR REPLACE INTO recordings(id, payload) VALUES (?, ?)",
            (recording_id, json.dumps(payload)),
        )
        conn.commit()
        conn.close()
        return jsonify(payload), 201

    @app.get("/api/recordings")
    def list_recordings():
        branch_name = request.args.get("branch")
        conn = _connect()
        rows = conn.execute("SELECT payload FROM recordings ORDER BY created_at DESC").fetchall()
        conn.close()

        results: List[Dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row["payload"])
            if branch_name and branch_name not in payload.get("branch_events", {}):
                continue
            results.append(
                {
                    "id": payload["id"],
                    "active_branch": payload.get("active_branch", "main"),
                    "branches": sorted(payload.get("branch_events", {}).keys()),
                    "event_count": len(payload.get("events", [])),
                }
            )

        return jsonify(results)

    @app.get("/api/recordings/<recording_id>")
    def get_recording(recording_id: str):
        branch_name = request.args.get("branch", "main")
        terminal_event_id = request.args.get("terminal_event_id")

        conn = _connect()
        row = conn.execute("SELECT payload FROM recordings WHERE id = ?", (recording_id,)).fetchone()
        conn.close()
        if not row:
            return jsonify({"error": "not_found"}), 404

        payload = json.loads(row["payload"])
        try:
            replay_events = resolve_branch_path(
                payload, branch_name=branch_name, terminal_event_id=terminal_event_id
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        response = dict(payload)
        response["replay_branch"] = branch_name
        response["replay_events"] = replay_events
        return jsonify(response)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
