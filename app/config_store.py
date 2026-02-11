from collections import defaultdict

from app.models import Role

DEFAULT_ROLE_ENABLEMENT: dict[Role, dict[str, bool]] = {
    Role.TEACHER: {
        "concept-explainer": True,
        "quiz-builder": True,
        "hint-coach": True,
    },
    Role.STUDENT: {
        "concept-explainer": True,
        "quiz-builder": False,
        "hint-coach": False,
    },
}

SESSION_ROLE_ENABLEMENT: dict[tuple[str, str], dict[Role, dict[str, bool]]] = defaultdict(
    lambda: {
        role: assistants.copy()
        for role, assistants in DEFAULT_ROLE_ENABLEMENT.items()
    }
)


def get_session_enablement(class_id: str, session_id: str) -> dict[Role, dict[str, bool]]:
    return SESSION_ROLE_ENABLEMENT[(class_id, session_id)]


def set_session_enablement(
    class_id: str,
    session_id: str,
    role_enablement: dict[Role, dict[str, bool]],
) -> dict[Role, dict[str, bool]]:
    SESSION_ROLE_ENABLEMENT[(class_id, session_id)] = {
        role: assistants.copy() for role, assistants in role_enablement.items()
    }
    return SESSION_ROLE_ENABLEMENT[(class_id, session_id)]
