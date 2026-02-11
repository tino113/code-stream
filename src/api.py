from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.policy_engine import AIInteractionService


class PolicyAPI:
    """Thin API facade to represent endpoint behavior."""

    def __init__(self, service: AIInteractionService) -> None:
        self.service = service

    def post_interaction(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.service.process_interaction(
            prompt=payload["prompt"],
            prompt_class=payload["prompt_class"],
            debug=payload.get("debug", False),
        )

    def get_safety_policy(self) -> dict[str, Any]:
        return self.service.get_safety_policy()

    def patch_teacher_controls(self, payload: dict[str, Any]) -> dict[str, Any]:
        controls = self.service.set_teacher_controls(
            strictness_level=payload.get("strictness_level"),
            student_privacy_redaction_default=payload.get("student_privacy_redaction_default"),
        )
        return {"teacher_controls": asdict(controls)}
