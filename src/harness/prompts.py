from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import questionary
from questionary import Style

from harness.config import HarnessConfig

PROMPT_STYLE = Style(
    [
        ("qmark", "fg:#00afff bold"),
        ("question", "bold"),
        ("pointer", "fg:#00afff bold"),
        ("highlighted", "noinherit"),
        ("selected", "noinherit"),
        ("answer", "fg:#00afff bold"),
        ("separator", "fg:#6c6c6c"),
        ("instruction", "fg:#6c6c6c"),
        ("text", ""),
        ("disabled", "fg:#6c6c6c italic"),
    ]
)

Validator = Callable[[str], bool | str]


class PromptCancelled(RuntimeError):
    pass


def ask_text(message: str, default: str = "", validate: Validator | None = None) -> str:
    return _answer(
        questionary.text(message, default=default, validate=validate, style=PROMPT_STYLE)
    )


def ask_confirm(message: str, default: bool = True) -> bool:
    return bool(
        _answer(questionary.confirm(message, default=default, style=PROMPT_STYLE))
    )


def collect_harness_config(target: Path) -> HarnessConfig:
    resolved_target = Path(target).expanduser().resolve()
    default_title = resolved_target.name or "my-project"
    title = ask_text("Project title", default=default_title, validate=_required("A project title"))
    description = ask_text(
        "Project description", validate=_required("A project description")
    )
    tech_stack = ask_text("Tech stack", validate=_required("A tech stack"))
    uses_docker = ask_confirm("Does this project use Docker?", default=False)
    config = HarnessConfig(
        app_name=title.strip(),
        description=description.strip(),
        tech_stack=tech_stack.strip(),
        uses_docker=uses_docker,
    )
    config.validate()
    return config


def _required(label: str) -> Validator:
    def validate(value: str) -> bool | str:
        return True if value.strip() else f"{label} is required."

    return validate


def _answer(question):
    try:
        answer = question.ask()
    except KeyboardInterrupt as error:
        raise PromptCancelled("Cancelled by user.") from error
    if answer is None:
        raise PromptCancelled("Cancelled by user.")
    return answer
