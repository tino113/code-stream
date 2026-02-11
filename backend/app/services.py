from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Iterable, List
from uuid import uuid4

from .models import Annotation, Checkpoint, CheckpointStatus, StudentPlaybackState


class InMemoryStore:
    def __init__(self) -> None:
        self.annotations: Dict[str, Annotation] = {}
        self.checkpoints: Dict[str, Checkpoint] = {}
        self.playback: Dict[str, StudentPlaybackState] = {}

    def list_checkpoints_by_timeline(self) -> List[Checkpoint]:
        return sorted(self.checkpoints.values(), key=lambda c: c.timestamp)


class CheckpointService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create_annotation(self, timestamp: float, note: str) -> Annotation:
        annotation = Annotation(id=str(uuid4()), timestamp=timestamp, note=note)
        self.store.annotations[annotation.id] = annotation
        return annotation

    def convert_annotation_to_checkpoint(
        self,
        annotation_id: str,
        prompt: str,
        expected_concept_tags: Iterable[str],
        unlock_condition: str,
    ) -> Checkpoint:
        annotation = self.store.annotations[annotation_id]
        checkpoint = Checkpoint(
            id=str(uuid4()),
            source_annotation_id=annotation.id,
            prompt=prompt,
            expected_concept_tags=list(expected_concept_tags),
            unlock_condition=unlock_condition,
            timestamp=annotation.timestamp,
        )
        self.store.checkpoints[checkpoint.id] = checkpoint
        return checkpoint

    def get_or_create_playback(self, student_id: str) -> StudentPlaybackState:
        if student_id not in self.store.playback:
            self.store.playback[student_id] = StudentPlaybackState(student_id=student_id)
        playback = self.store.playback[student_id]
        for checkpoint in self.store.checkpoints.values():
            playback.ensure_checkpoint(checkpoint.id)
        return playback

    def update_checkpoint_state(
        self,
        student_id: str,
        checkpoint_id: str,
        action: str,
        used_hint: bool = False,
        runtime_success: bool = False,
    ) -> Dict:
        playback = self.get_or_create_playback(student_id)
        checkpoint_state = playback.ensure_checkpoint(checkpoint_id)

        if action == "attempt":
            checkpoint_state.mark_attempt(used_hint=used_hint, runtime_success=runtime_success)
        elif action == "pass":
            checkpoint_state.mark_passed()
        elif action == "unlock":
            checkpoint_state.mark_unlocked()
        else:
            raise ValueError(f"Unknown action '{action}'")

        return asdict(checkpoint_state)

    def calculate_rubric_score(self, student_id: str, checkpoint_id: str) -> Dict:
        playback = self.get_or_create_playback(student_id)
        state = playback.ensure_checkpoint(checkpoint_id)

        if state.attempt_count == 0:
            attempts_score = 0.0
        elif state.attempt_count == 1:
            attempts_score = 1.0
        elif state.attempt_count == 2:
            attempts_score = 0.8
        else:
            attempts_score = 0.5

        hint_ratio = state.hint_count / state.attempt_count if state.attempt_count else 0.0
        hint_score = max(0.0, 1.0 - hint_ratio)
        runtime_score = 1.0 if state.runtime_success_count > 0 else 0.0

        total = round((attempts_score * 0.3) + (hint_score * 0.3) + (runtime_score * 0.4), 2)

        return {
            "checkpoint_id": checkpoint_id,
            "student_id": student_id,
            "signals": {
                "attempt_count": state.attempt_count,
                "hint_count": state.hint_count,
                "runtime_success_count": state.runtime_success_count,
                "status": state.status.value if isinstance(state.status, CheckpointStatus) else state.status,
            },
            "rubric": {
                "attempts_score": attempts_score,
                "hint_dependence_score": hint_score,
                "runtime_success_score": runtime_score,
                "total": total,
            },
        }
