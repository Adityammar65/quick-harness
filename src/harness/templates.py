from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

from harness.adapters import display_names
from harness.config import (
    MODE_LABELS,
    ROLE_LABELS,
    GenerationMode,
    HarnessConfig,
    Role,
    ensure_safe_relative_path,
    ordered_roles,
)

TEMPLATE_DIRECTORY = Path(__file__).resolve().parent / "templates"
PRESET_DIRECTORY = Path(__file__).resolve().parent / "presets"
AGENTS_TEMPLATE = "agents.md.j2"
ROLE_TEMPLATE = "roles/{role}.md.j2"


class TemplateError(RuntimeError):
    pass


@dataclass(frozen=True)
class Preset:
    name: str
    title: str
    description: str
    conventions: tuple[str, ...]
    commands: tuple[str, ...]


def build_environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIRECTORY),
        autoescape=False,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def preset_names() -> tuple[str, ...]:
    return tuple(sorted(path.stem for path in PRESET_DIRECTORY.glob("*.json")))


def load_preset(name: str) -> Preset:
    ensure_safe_relative_path(name, "Preset")
    path = PRESET_DIRECTORY / f"{name}.json"
    if not path.is_file():
        available = ", ".join(preset_names()) or "none"
        raise TemplateError(f"Unknown preset: {name}. Available presets: {available}.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TemplateError(f"Could not read preset {name}: {error}") from error

    title = data.get("title")
    description = data.get("description")
    conventions = data.get("conventions") or []
    commands = data.get("commands") or []
    if not isinstance(title, str) or not title.strip():
        raise TemplateError(f"Preset {name} is missing a title.")
    if not isinstance(description, str):
        raise TemplateError(f"Preset {name} description must be a string.")
    if not isinstance(conventions, list) or not all(
        isinstance(entry, str) for entry in conventions
    ):
        raise TemplateError(f"Preset {name} has invalid conventions.")
    if not isinstance(commands, list) or not all(isinstance(entry, str) for entry in commands):
        raise TemplateError(f"Preset {name} has invalid commands.")

    return Preset(
        name=name,
        title=title.strip(),
        description=description.strip(),
        conventions=tuple(conventions),
        commands=tuple(commands),
    )


def available_presets() -> tuple[Preset, ...]:
    return tuple(load_preset(name) for name in preset_names())


def render_agents_md(config: HarnessConfig) -> str:
    config.validate()
    preset = load_preset(config.preset)
    environment = build_environment()
    roles = ordered_roles(config.roles)
    role_sections = tuple(
        _render_role_section(environment, role) for role in roles
    )
    show_preset = config.mode in (GenerationMode.TEMPLATE, GenerationMode.HYBRID)
    show_custom_rules = (
        config.mode in (GenerationMode.CUSTOM, GenerationMode.HYBRID)
        and bool(config.custom_rules)
    )
    cross_layer = Role.FRONTEND in roles and Role.BACKEND in roles

    rendered = environment.get_template(AGENTS_TEMPLATE).render(
        config=config,
        preset=preset,
        mode_label=MODE_LABELS[config.mode],
        role_labels=", ".join(ROLE_LABELS[role] for role in roles),
        agent_labels=display_names(config.agents),
        role_sections=role_sections,
        cross_layer=cross_layer,
        show_preset=show_preset,
        show_custom_rules=show_custom_rules,
    )
    return normalize_markdown(rendered)


def normalize_markdown(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip("\n")
    return f"{normalized}\n"


def _render_role_section(environment: Environment, role: Role) -> str:
    template_name = ROLE_TEMPLATE.format(role=role.value)
    try:
        rendered = environment.get_template(template_name).render()
    except TemplateNotFound as error:
        raise TemplateError(f"Missing role template: {template_name}") from error
    return normalize_markdown(rendered).strip()
