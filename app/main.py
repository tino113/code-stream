from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.config_store import get_session_enablement, set_session_enablement
from app.models import (
    AssistantGatewayRequest,
    AssistantGatewayResponse,
    Role,
    SessionEnablementUpdate,
    SessionEnablementView,
)
from app.policy import PolicyViolation, enforce_output_policy
from app.registry import ASSISTANT_REGISTRY, FEATURE_FLAG_REGISTRY

app = FastAPI(title="Assistant Gateway")


@app.get("/")
def teacher_ui() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "teacher.html")


@app.get("/api/assistants")
def list_assistants() -> dict[str, object]:
    return {
        "assistants": [
            {
                "assistant_id": contract.assistant_id,
                "name": contract.name,
                "output_type": contract.output_type,
                "feature_enabled": FEATURE_FLAG_REGISTRY.get(contract.assistant_id, False),
            }
            for contract in ASSISTANT_REGISTRY.values()
        ]
    }


@app.get("/api/teacher/config/{class_id}/{session_id}", response_model=SessionEnablementView)
def get_teacher_config(class_id: str, session_id: str) -> SessionEnablementView:
    return SessionEnablementView(
        class_id=class_id,
        session_id=session_id,
        effective_enablement=get_session_enablement(class_id, session_id),
    )


@app.put("/api/teacher/config", response_model=SessionEnablementView)
def put_teacher_config(payload: SessionEnablementUpdate) -> SessionEnablementView:
    merged = {role.role: role.assistants for role in payload.role_enablement}
    for role in Role:
        merged.setdefault(role, {})
    effective = set_session_enablement(payload.class_id, payload.session_id, merged)
    return SessionEnablementView(
        class_id=payload.class_id,
        session_id=payload.session_id,
        effective_enablement=effective,
    )


@app.post("/api/assistant/gateway", response_model=AssistantGatewayResponse)
def assistant_gateway(payload: AssistantGatewayRequest) -> AssistantGatewayResponse:
    contract = ASSISTANT_REGISTRY.get(payload.assistant_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Assistant not found")

    if not FEATURE_FLAG_REGISTRY.get(payload.assistant_id, False):
        raise HTTPException(status_code=403, detail="Assistant disabled by feature flag")

    session_policy = get_session_enablement(payload.context.class_id, payload.context.session_id)
    if not session_policy[payload.context.role].get(payload.assistant_id, False):
        raise HTTPException(status_code=403, detail="Assistant disabled for this role/session")

    if payload.context.role.value not in contract.accepted_roles:
        raise HTTPException(status_code=403, detail="Role not allowed for this assistant")

    output = contract.generate(payload.context)

    try:
        notes = enforce_output_policy(output, contract)
    except PolicyViolation as err:
        raise HTTPException(status_code=422, detail=str(err)) from err

    return AssistantGatewayResponse(
        assistant_id=payload.assistant_id,
        output=output,
        policy_notes=notes,
    )
