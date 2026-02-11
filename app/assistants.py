from app.models import (
    AssistantInputContext,
    HintOutput,
    QuizOutput,
    QuizQuestion,
    TextOutput,
)


def concept_explainer(context: AssistantInputContext) -> TextOutput:
    return TextOutput(content=f"Concept summary: {context.prompt.strip().capitalize()}.")


def quiz_builder(context: AssistantInputContext) -> QuizOutput:
    return QuizOutput(
        quiz=QuizQuestion(
            prompt=f"What is a key idea in: {context.prompt}?",
            options=["Main concept", "Random guess", "Unrelated fact"],
            answer_index=0,
        )
    )


def hint_coach(context: AssistantInputContext) -> HintOutput:
    return HintOutput(hint=f"Hint: break '{context.prompt}' into smaller steps.")
