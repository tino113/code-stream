from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class CheckpointStatus(str, Enum):
    ASSIGNED = "assigned"
    ATTEMPTED = "attempted"
    PASSED = "passed"
    UNLOCKED = "unlocked"


@dataclass
class Annotation:
    id: str
    timestamp: float
    note: str


@dataclass
class Checkpoint:
    id: str
    source_annotation_id: str
    prompt: str
    expected_concept_tags: List[str]
    unlock_condition: str
    timestamp: float


@dataclass
class StudentCheckpointState:
    checkpoint_id: str
    status: CheckpointStatus = CheckpointStatus.ASSIGNED
    attempt_count: int = 0
    hint_count: int = 0
    runtime_success_count: int = 0

    def mark_attempt(self, used_hint: bool, runtime_success: bool) -> None:
        self.attempt_count += 1
        if used_hint:
            self.hint_count += 1
        if runtime_success:
            self.runtime_success_count += 1
        if self.status == CheckpointStatus.ASSIGNED:
            self.status = CheckpointStatus.ATTEMPTED

    def mark_passed(self) -> None:
        self.status = CheckpointStatus.PASSED

    def mark_unlocked(self) -> None:
        self.status = CheckpointStatus.UNLOCKED


@dataclass
class StudentPlaybackState:
    student_id: str
    current_time: float = 0
    checkpoint_states: Dict[str, StudentCheckpointState] = field(default_factory=dict)

    def ensure_checkpoint(self, checkpoint_id: str) -> StudentCheckpointState:
        if checkpoint_id not in self.checkpoint_states:
            self.checkpoint_states[checkpoint_id] = StudentCheckpointState(checkpoint_id=checkpoint_id)
        return self.checkpoint_states[checkpoint_id]
