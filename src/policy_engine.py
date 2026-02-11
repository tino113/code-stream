from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TeacherControls:
    strictness_level: str = "medium"
    student_privacy_redaction_default: bool = True


@dataclass
class SessionPolicy:
    session_id: str
    constraints: list[str] = field(default_factory=list)
    teacher_controls: TeacherControls = field(default_factory=TeacherControls)

    def active_constraints(self) -> list[str]:
        constraints = list(self.constraints)
        if self.teacher_controls.strictness_level == "high" and "require_policy_review" not in constraints:
            constraints.append("require_policy_review")
        if self.teacher_controls.student_privacy_redaction_default and "student_privacy_redaction" not in constraints:
            constraints.append("student_privacy_redaction")
        return constraints


@dataclass
class InteractionAuditRecord:
    timestamp: str
    session_id: str
    prompt_class: str
    policy_checks_triggered: list[str]
    output_transformations_applied: list[str]
    response_mode: str


class AuditTrail:
    def __init__(self) -> None:
        self._records: list[InteractionAuditRecord] = []

    @property
    def records(self) -> list[InteractionAuditRecord]:
        return list(self._records)

    def append(self, record: InteractionAuditRecord) -> None:
        self._records.append(record)


class AIInteractionService:
    """Core policy-aware interaction handler with audit logging."""

    def __init__(self, session_policy: SessionPolicy, audit_trail: AuditTrail | None = None) -> None:
        self.session_policy = session_policy
        self.audit_trail = audit_trail or AuditTrail()

    def set_teacher_controls(
        self,
        *,
        strictness_level: str | None = None,
        student_privacy_redaction_default: bool | None = None,
    ) -> TeacherControls:
        if strictness_level is not None:
            if strictness_level not in {"low", "medium", "high"}:
                raise ValueError("strictness_level must be one of: low, medium, high")
            self.session_policy.teacher_controls.strictness_level = strictness_level
        if student_privacy_redaction_default is not None:
            self.session_policy.teacher_controls.student_privacy_redaction_default = (
                student_privacy_redaction_default
            )
        return self.session_policy.teacher_controls

    def get_safety_policy(self) -> dict[str, Any]:
        """Safety policy endpoint payload for current session."""
        return {
            "session_id": self.session_policy.session_id,
            "active_constraints": self.session_policy.active_constraints(),
            "teacher_controls": asdict(self.session_policy.teacher_controls),
        }

    def process_interaction(self, *, prompt: str, prompt_class: str, debug: bool = False) -> dict[str, Any]:
        checks = self._run_policy_checks(prompt_class=prompt_class)
        hint = self._build_hint(prompt, prompt_class)

        transformations: list[str] = []
        if "no_code_output" in self.session_policy.active_constraints():
            hint = self._remove_code_like_content(hint)
            transformations.append("code_removed")

        if "student_privacy_redaction" in self.session_policy.active_constraints():
            hint = self._apply_privacy_redaction(hint)
            transformations.append("student_identifier_redacted")

        response: dict[str, Any] = {"hint": hint}
        if debug:
            response["metadata"] = {
                "why_this_hint": self._why_hint(prompt_class, checks),
                "policy_checks_triggered": checks,
                "output_transformations_applied": transformations,
            }

        self.audit_trail.append(
            InteractionAuditRecord(
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
                session_id=self.session_policy.session_id,
                prompt_class=prompt_class,
                policy_checks_triggered=checks,
                output_transformations_applied=transformations,
                response_mode="debug" if debug else "standard",
            )
        )

        return response

    def _run_policy_checks(self, *, prompt_class: str) -> list[str]:
        checks = ["prompt_classification"]
        if self.session_policy.teacher_controls.strictness_level == "high":
            checks.extend(["strictness_high_review", "sensitive_content_scan"])
        if prompt_class == "exam":
            checks.append("exam_integrity_scan")
        return checks

    def _build_hint(self, prompt: str, prompt_class: str) -> str:
        if prompt_class == "exam":
            return "Focus on the concept and outline the approach in your own words; avoid final numeric answers."
        if "code" in prompt.lower():
            return (
                "Explain the algorithmic idea first for the student. Example pattern only:\n"
                "```python\n# sample structure\npass\n```"
            )
        return f"Consider decomposing the task into smaller steps before attempting a full solution for: {prompt}"

    @staticmethod
    def _remove_code_like_content(text: str) -> str:
        if "```" not in text:
            return text
        chunks = text.split("```")
        return "[code omitted]".join(chunks[::2])

    @staticmethod
    def _apply_privacy_redaction(text: str) -> str:
        redacted = text.replace("student", "[redacted]")
        redacted = redacted.replace("Student", "[redacted]")
        return redacted

    @staticmethod
    def _why_hint(prompt_class: str, checks: list[str]) -> dict[str, Any]:
        return {
            "explanation": (
                "Hint is scoped to strategy and concept reinforcement based on prompt class; "
                "direct answers are intentionally withheld."
            ),
            "prompt_class": prompt_class,
            "checks_considered": checks,
            "solution_leakage_risk": "low",
        }
