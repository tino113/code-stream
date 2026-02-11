from src.api import PolicyAPI
from src.policy_engine import AIInteractionService, AuditTrail, SessionPolicy


def build_api(constraints=None):
    policy = SessionPolicy(session_id="sess-123", constraints=constraints or [])
    service = AIInteractionService(session_policy=policy, audit_trail=AuditTrail())
    return PolicyAPI(service), service


def test_safety_policy_endpoint_reports_active_constraints_and_controls():
    api, _ = build_api(constraints=["no_code_output"])

    payload = api.get_safety_policy()

    assert payload["session_id"] == "sess-123"
    assert "no_code_output" in payload["active_constraints"]
    assert "student_privacy_redaction" in payload["active_constraints"]
    assert payload["teacher_controls"]["strictness_level"] == "medium"


def test_teacher_controls_endpoint_updates_strictness_and_redaction_defaults():
    api, _ = build_api()

    response = api.patch_teacher_controls(
        {"strictness_level": "high", "student_privacy_redaction_default": False}
    )

    assert response["teacher_controls"] == {
        "strictness_level": "high",
        "student_privacy_redaction_default": False,
    }
    policy = api.get_safety_policy()
    assert "require_policy_review" in policy["active_constraints"]
    assert "student_privacy_redaction" not in policy["active_constraints"]


def test_policy_enforcement_blocks_code_and_logs_transformations():
    api, service = build_api(constraints=["no_code_output"])

    response = api.post_interaction(
        {
            "prompt": "student asks for exact code",
            "prompt_class": "homework",
            "debug": True,
        }
    )

    assert "code_removed" in response["metadata"]["output_transformations_applied"]
    assert "student_identifier_redacted" in response["metadata"]["output_transformations_applied"]
    assert "[redacted]" in response["hint"]
    assert len(service.audit_trail.records) == 1
    assert service.audit_trail.records[0].prompt_class == "homework"


def test_debug_why_this_hint_metadata_is_transparent_and_non_solution():
    api, _ = build_api(constraints=["no_code_output"])

    response = api.post_interaction(
        {"prompt": "integrate x^2", "prompt_class": "exam", "debug": True}
    )

    why = response["metadata"]["why_this_hint"]
    assert why["prompt_class"] == "exam"
    assert why["solution_leakage_risk"] == "low"
    assert "direct answers" in why["explanation"]
    assert "prompt_classification" in response["metadata"]["policy_checks_triggered"]
    assert "exam_integrity_scan" in response["metadata"]["policy_checks_triggered"]


def test_audit_trail_completeness_for_each_interaction():
    api, service = build_api(constraints=["no_code_output"])
    api.patch_teacher_controls({"strictness_level": "high"})

    api.post_interaction({"prompt": "help", "prompt_class": "exam", "debug": True})

    record = service.audit_trail.records[0]
    assert record.timestamp
    assert record.session_id == "sess-123"
    assert record.prompt_class == "exam"
    assert "strictness_high_review" in record.policy_checks_triggered
    assert "exam_integrity_scan" in record.policy_checks_triggered
    assert set(record.output_transformations_applied) == {
        "code_removed",
        "student_identifier_redacted",
    }
    assert record.response_mode == "debug"
