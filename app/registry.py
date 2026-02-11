from app.assistants import concept_explainer, hint_coach, quiz_builder
from app.contracts import AssistantContract, SafetyConstraints
from app.models import ResponseType

FEATURE_FLAG_REGISTRY: dict[str, bool] = {
    "concept-explainer": True,
    "quiz-builder": True,
    "hint-coach": True,
}

ASSISTANT_REGISTRY: dict[str, AssistantContract] = {
    "concept-explainer": AssistantContract(
        assistant_id="concept-explainer",
        name="Concept Explainer",
        accepted_roles=("teacher", "student"),
        output_type=ResponseType.TEXT,
        constraints=SafetyConstraints(
            max_chars=280,
            blocklist=("violent", "hate", "sexual"),
        ),
        generate=concept_explainer,
    ),
    "quiz-builder": AssistantContract(
        assistant_id="quiz-builder",
        name="Quiz Builder",
        accepted_roles=("teacher",),
        output_type=ResponseType.QUIZ,
        constraints=SafetyConstraints(
            max_chars=500,
            blocklist=("answer key leak",),
        ),
        generate=quiz_builder,
    ),
    "hint-coach": AssistantContract(
        assistant_id="hint-coach",
        name="Hint Coach",
        accepted_roles=("teacher", "student"),
        output_type=ResponseType.HINT,
        constraints=SafetyConstraints(
            max_chars=180,
            blocklist=("do it for you", "cheat"),
        ),
        generate=hint_coach,
    ),
}
