from __future__ import annotations

from dataclasses import asdict

from flask import Flask, jsonify, render_template, request

from .services import CheckpointService, InMemoryStore


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    store = InMemoryStore()
    service = CheckpointService(store)

    # Seed demo annotation and checkpoint for immediate use on student page.
    annotation = service.create_annotation(timestamp=15.0, note="Discuss loop invariants")
    service.convert_annotation_to_checkpoint(
        annotation_id=annotation.id,
        prompt="Explain why the loop invariant guarantees correctness.",
        expected_concept_tags=["loop-invariant", "correctness"],
        unlock_condition="pass_checkpoint",
    )

    @app.get("/student")
    def student() -> str:
        checkpoints = [asdict(c) for c in store.list_checkpoints_by_timeline()]
        return render_template("student.html", checkpoints=checkpoints)

    @app.post("/api/teacher/annotations")
    def create_annotation():
        payload = request.get_json(force=True)
        annotation = service.create_annotation(timestamp=payload["timestamp"], note=payload["note"])
        return jsonify(asdict(annotation)), 201

    @app.post("/api/teacher/checkpoints")
    def create_checkpoint():
        payload = request.get_json(force=True)
        checkpoint = service.convert_annotation_to_checkpoint(
            annotation_id=payload["annotation_id"],
            prompt=payload["prompt"],
            expected_concept_tags=payload.get("expected_concept_tags", []),
            unlock_condition=payload["unlock_condition"],
        )
        return jsonify(asdict(checkpoint)), 201

    @app.get("/api/student/<student_id>/playback")
    def get_playback(student_id: str):
        playback = service.get_or_create_playback(student_id)
        serialized = {
            "student_id": playback.student_id,
            "current_time": playback.current_time,
            "checkpoint_states": {
                checkpoint_id: asdict(state) for checkpoint_id, state in playback.checkpoint_states.items()
            },
            "checkpoints": [asdict(c) for c in store.list_checkpoints_by_timeline()],
        }
        return jsonify(serialized)

    @app.post("/api/student/<student_id>/checkpoints/<checkpoint_id>/state")
    def update_checkpoint_state(student_id: str, checkpoint_id: str):
        payload = request.get_json(force=True)
        state = service.update_checkpoint_state(
            student_id=student_id,
            checkpoint_id=checkpoint_id,
            action=payload["action"],
            used_hint=payload.get("used_hint", False),
            runtime_success=payload.get("runtime_success", False),
        )
        return jsonify(state)

    @app.get("/api/student/<student_id>/checkpoints/<checkpoint_id>/rubric")
    def checkpoint_rubric(student_id: str, checkpoint_id: str):
        return jsonify(service.calculate_rubric_score(student_id=student_id, checkpoint_id=checkpoint_id))

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=True)
