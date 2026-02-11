import pytest

from app.config_store import DEFAULT_ROLE_ENABLEMENT, SESSION_ROLE_ENABLEMENT
from app.registry import FEATURE_FLAG_REGISTRY


@pytest.fixture(autouse=True)
def reset_state():
    SESSION_ROLE_ENABLEMENT.clear()
    FEATURE_FLAG_REGISTRY.update(
        {
            "concept-explainer": True,
            "quiz-builder": True,
            "hint-coach": True,
        }
    )
    yield
    SESSION_ROLE_ENABLEMENT.clear()
    for role, assistants in DEFAULT_ROLE_ENABLEMENT.items():
        DEFAULT_ROLE_ENABLEMENT[role] = assistants.copy()
