from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import questionary
from questionary import Choice
from rich.console import Console

from harness import generator, skills, templates
from harness.adapters import all_adapters, resolve_skills_directory
from harness.config import (
    DEFAULT_PRESET,
    MODE_LABELS,
    ROLE_LABELS,
    ROLE_ORDER,
    GenerationMode,
    GitIgnoreChoice,
    HarnessConfig,
    Role,
    SkillSelection,
)

console = Console()

Validator = Callable[[str], bool | str]


class PromptCancelled(RuntimeError):
    pass


def ask_text(message: str, default: str = "", validate: Validator | None = None) -> str:
    return _answer(questionary.text(message, default=default, validate=validate))


def ask_select(message: str, choices: list[Choice], default: object | None = None):
    return _answer(questionary.select(message, choices=choices, default=default))


def ask_checkbox(
    message: str, choices: list[Choice], defaults: tuple[object, ...] = ()
) -> list:
    prepared = [
        Choice(choice.title, value=choice.value, checked=choice.value in defaults)
        for choice in choices
    ]
    return _answer(questionary.checkbox(message, choices=prepared))


def ask_confirm(message: str, default: bool = True) -> bool:
    return bool(_answer(questionary.confirm(message, default=default)))


def parse_rule_lines(text: str) -> tuple[str, ...]:
    rules = []
    for line in text.splitlines():
        stripped = line.strip().lstrip("-*").strip()
        if stripped:
            rules.append(stripped)
    return tuple(rules)


def collect_harness_config(target: Path) -> HarnessConfig:
    resolved_target = Path(target).expanduser().resolve()
    default_name = resolved_target.name or "my-project"

    app_name = ask_text(
        "Application name", default=default_name, validate=_required("An application name")
    )
    description = ask_text(
        "Application description", validate=_required("An application description")
    )
    mode = ask_select(
        "Generation mode",
        choices=[Choice(MODE_LABELS[value], value=value) for value in GenerationMode],
        default=GenerationMode.HYBRID,
    )
    roles = ask_checkbox(
        "Agent roles",
        choices=[Choice(ROLE_LABELS[role], value=role) for role in ROLE_ORDER],
        defaults=(Role.FULLSTACK,),
    )
    if not roles:
        raise PromptCancelled("Select at least one role.")

    agents = ask_checkbox(
        "Target agents",
        choices=[
            Choice(
                f"{adapter.display_name} (skills in {adapter.skills_directory or 'skills'})",
                value=adapter.name,
            )
            for adapter in all_adapters()
        ],
        defaults=("claude",),
    )

    preset_name = DEFAULT_PRESET
    if mode in (GenerationMode.TEMPLATE, GenerationMode.HYBRID):
        preset_name = ask_select(
            "Preset",
            choices=[
                Choice(f"{preset.title} — {preset.description}", value=preset.name)
                for preset in templates.available_presets()
            ],
            default=DEFAULT_PRESET,
        )

    custom_rules: tuple[str, ...] = ()
    if mode in (GenerationMode.CUSTOM, GenerationMode.HYBRID):
        custom_rules = _collect_custom_rules(required=mode is GenerationMode.CUSTOM)

    selected_skills = _collect_skills()
    skills_directory = ask_text(
        "Skills directory",
        default=resolve_skills_directory(agents),
        validate=_required("A skills directory"),
    )

    config = HarnessConfig(
        app_name=app_name.strip(),
        description=description.strip(),
        mode=mode,
        roles=tuple(roles),
        agents=tuple(agents),
        preset=preset_name,
        custom_rules=custom_rules,
        skills=selected_skills,
        skills_directory=skills_directory.strip(),
    )

    config = _collect_gitignore(config)
    config.validate()
    return config


def _collect_custom_rules(required: bool) -> tuple[str, ...]:
    rules: list[str] = []
    prompt = "Additional rule, or leave empty to finish"
    while True:
        if required and not rules:
            console.print("Custom mode requires at least one rule.", style="yellow")
        answer = ask_text(prompt, default="")
        parsed = parse_rule_lines(answer)
        if parsed:
            rules.extend(parsed)
            continue
        if rules:
            break
        if not required:
            break
    return tuple(rules)


def _collect_skills() -> tuple[SkillSelection, ...]:
    catalog = skills.load_catalog()
    selections: list[SkillSelection] = []
    chosen = ask_checkbox(
        "Skills from the built-in catalog",
        choices=[
            Choice(f"{entry.name} — {entry.description}", value=entry.name)
            for entry in catalog
        ],
    )
    for entry in catalog:
        if entry.name in chosen:
            selections.append(
                SkillSelection(
                    name=entry.name,
                    source=entry.repo_url,
                    subdirectory=entry.subdirectory,
                    license=entry.license,
                )
            )

    custom_url = ask_text(
        "Custom skill Git URL or local path, or leave empty to skip", default=""
    ).strip()
    if custom_url:
        subdirectory = ask_text(
            "Subdirectory containing the skill, or leave empty for the repository root",
            default="",
        ).strip()
        selections.append(
            SkillSelection(
                name=None,
                source=custom_url,
                subdirectory=subdirectory or None,
                license=None,
            )
        )
    return tuple(selections)


def _collect_gitignore(config: HarnessConfig) -> HarnessConfig:
    choices = [
        Choice(
            "No — keep the generated files trackable (recommended)",
            value=GitIgnoreChoice.NO,
        ),
        Choice("Yes — ignore every generated path", value=GitIgnoreChoice.YES),
        Choice("Custom — choose individual paths", value=GitIgnoreChoice.CUSTOM),
    ]
    choice = ask_select(".gitignore handling", choices=choices, default=GitIgnoreChoice.NO)
    if choice is GitIgnoreChoice.NO:
        return replace(config, gitignore=GitIgnoreChoice.NO, gitignore_paths=())

    paths = generator.generated_paths(config)
    if choice is GitIgnoreChoice.YES:
        return replace(config, gitignore=GitIgnoreChoice.YES, gitignore_paths=paths)

    selected = ask_checkbox(
        "Paths to add to .gitignore",
        choices=[Choice(path, value=path) for path in paths],
    )
    return replace(
        config,
        gitignore=GitIgnoreChoice.CUSTOM,
        gitignore_paths=tuple(selected),
    )


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
