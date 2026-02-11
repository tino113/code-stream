from dataclasses import replace

from fastapi.testclient import TestClient

from app.main import app
from app.models import TextOutput
from app.registry import ASSISTANT_REGISTRY, FEATURE_FLAG_REGISTRY

client = TestClient(app)


def gateway_payload(assistant_id: str, role: str = "student", prompt: str = "fractions") -> dict:
    return {
        "assistant_id": assistant_id,
        "context": {
            "class_id": "math-101",
            "session_id": "fall-week-2",
            "role": role,
            "user_id": "u-1",
            "prompt": prompt,
        },
    }


def test_feature_flag_enforcement_blocks_assistant():
    FEATURE_FLAG_REGISTRY["concept-explainer"] = False
    response = client.post("/api/assistant/gateway", json=gateway_payload("concept-explainer"))
    assert response.status_code == 403
    assert response.json()["detail"] == "Assistant disabled by feature flag"


def test_session_role_policy_blocks_student_assistant_use():
    response = client.put(
        "/api/teacher/config",
        json={
            "class_id": "math-101",
            "session_id": "fall-week-2",
            "role_enablement": [
                {"role": "student", "assistants": {"concept-explainer": False}},
            ],
        },
    )
    assert response.status_code == 200

    blocked = client.post("/api/assistant/gateway", json=gateway_payload("concept-explainer"))
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "Assistant disabled for this role/session"


def test_policy_guardrail_for_text_response_type():
    contract = ASSISTANT_REGISTRY["concept-explainer"]
    ASSISTANT_REGISTRY["concept-explainer"] = replace(
        contract,
        generate=lambda _ctx: TextOutput(content="hate"),
    )

    response = client.post("/api/assistant/gateway", json=gateway_payload("concept-explainer"))
    assert response.status_code == 422
    assert "safety policy" in response.json()["detail"]

    ASSISTANT_REGISTRY["concept-explainer"] = contract


def test_policy_guardrail_for_quiz_response_type():
    response = client.post("/api/assistant/gateway", json=gateway_payload("quiz-builder", role="teacher"))
    assert response.status_code == 200
    assert response.json()["output"]["response_type"] == "quiz"
    assert "quiz-content-checked" in response.json()["policy_notes"]


def test_policy_guardrail_for_hint_response_type():
    client.put(
        "/api/teacher/config",
        json={
            "class_id": "math-101",
            "session_id": "fall-week-2",
            "role_enablement": [
                {
                    "role": "student",
                    "assistants": {
                        "hint-coach": True,
                        "concept-explainer": True,
                        "quiz-builder": False,
                    },
                },
            ],
        },
    )

    response = client.post("/api/assistant/gateway", json=gateway_payload("hint-coach"))
    assert response.status_code == 200
    assert response.json()["output"]["response_type"] == "hint"
    assert "hint-content-checked" in response.json()["policy_notes"]
