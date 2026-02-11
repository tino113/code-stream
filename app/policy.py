from app.contracts import AssistantContract
from app.models import AssistantOutput, HintOutput, QuizOutput, TextOutput


class PolicyViolation(Exception):
    pass


def _scan_text(value: str, contract: AssistantContract) -> None:
    lowered = value.lower()
    if len(value) > contract.constraints.max_chars:
        raise PolicyViolation("Output exceeds maximum allowed size")
    for blocked in contract.constraints.blocklist:
        if blocked in lowered:
            raise PolicyViolation(f"Output violated safety policy: {blocked}")


def enforce_output_policy(output: AssistantOutput, contract: AssistantContract) -> list[str]:
    notes: list[str] = []
    if isinstance(output, TextOutput):
        _scan_text(output.content, contract)
        notes.append("text-content-checked")
    elif isinstance(output, QuizOutput):
        _scan_text(output.quiz.prompt, contract)
        for option in output.quiz.options:
            _scan_text(option, contract)
        notes.append("quiz-content-checked")
    elif isinstance(output, HintOutput):
        _scan_text(output.hint, contract)
        notes.append("hint-content-checked")
    return notes
