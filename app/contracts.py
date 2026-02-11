from dataclasses import dataclass
from typing import Callable

from app.models import AssistantInputContext, AssistantOutput, ResponseType


@dataclass(frozen=True)
class SafetyConstraints:
    max_chars: int
    blocklist: tuple[str, ...]


@dataclass(frozen=True)
class AssistantContract:
    assistant_id: str
    name: str
    accepted_roles: tuple[str, ...]
    output_type: ResponseType
    constraints: SafetyConstraints
    generate: Callable[[AssistantInputContext], AssistantOutput]
