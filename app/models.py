from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Role(str, Enum):
    TEACHER = "teacher"
    STUDENT = "student"


class ResponseType(str, Enum):
    TEXT = "text"
    QUIZ = "quiz"
    HINT = "hint"


class AssistantInputContext(BaseModel):
    class_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    role: Role
    user_id: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)


class TextOutput(BaseModel):
    response_type: Literal[ResponseType.TEXT] = ResponseType.TEXT
    content: str


class QuizQuestion(BaseModel):
    prompt: str
    options: list[str]
    answer_index: int


class QuizOutput(BaseModel):
    response_type: Literal[ResponseType.QUIZ] = ResponseType.QUIZ
    quiz: QuizQuestion


class HintOutput(BaseModel):
    response_type: Literal[ResponseType.HINT] = ResponseType.HINT
    hint: str


AssistantOutput = TextOutput | QuizOutput | HintOutput


class AssistantGatewayRequest(BaseModel):
    assistant_id: str
    context: AssistantInputContext


class AssistantGatewayResponse(BaseModel):
    assistant_id: str
    output: AssistantOutput
    policy_notes: list[str] = []


class RoleEnablement(BaseModel):
    role: Role
    assistants: dict[str, bool]


class SessionEnablementUpdate(BaseModel):
    class_id: str
    session_id: str
    role_enablement: list[RoleEnablement]


class SessionEnablementView(BaseModel):
    class_id: str
    session_id: str
    effective_enablement: dict[Role, dict[str, bool]]
