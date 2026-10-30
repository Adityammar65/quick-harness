from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath

DEFAULT_DOC_FILES = (
    "project-overview.md",
    "architecture.md",
    "conventions.md",
    "workflow.md",
)
DEFAULT_PRESET = "general"
DEFAULT_SKILLS_DIRECTORY = "skills"
INSTRUCTION_FILE = "AGENTS.md"
GITIGNORE_FILE = ".gitignore"
DOCS_DIRECTORY = "docs"

SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
GITIGNORE_BLOCKED_ENTRIES = {"*", "/*", "**", "**/*", "/", "/**"}


class ConfigurationError(ValueError):
    pass


class GenerationMode(str, Enum):
    TEMPLATE = "template"
    CUSTOM = "custom"
    HYBRID = "hybrid"


class Role(str, Enum):
    FRONTEND = "frontend"
    BACKEND = "backend"
    FULLSTACK = "fullstack"


class GitIgnoreChoice(str, Enum):
    NO = "no"
    DEFAULT = "default"
    CUSTOM = "custom"


MODE_LABELS = {
    GenerationMode.TEMPLATE: "Template (predefined instructions)",
    GenerationMode.CUSTOM: "Custom (user-defined rules)",
    GenerationMode.HYBRID: "Hybrid (predefined instructions plus custom rules)",
}

ROLE_LABELS = {
    Role.FRONTEND: "Frontend",
    Role.BACKEND: "Backend",
    Role.FULLSTACK: "Fullstack",
}

ROLE_ORDER = (Role.FRONTEND, Role.BACKEND, Role.FULLSTACK)


@dataclass(frozen=True)
class SkillSelection:
    source: str
    name: str | None = None
    subdirectory: str | None = None
    license: str | None = None


@dataclass(frozen=True)
class HarnessConfig:
    app_name: str
    description: str
    mode: GenerationMode = GenerationMode.HYBRID
    roles: tuple[Role, ...] = (Role.FULLSTACK,)
    agents: tuple[str, ...] = ()
    preset: str = DEFAULT_PRESET
    custom_rules: tuple[str, ...] = ()
    skills: tuple[SkillSelection, ...] = ()
    gitignore: GitIgnoreChoice = GitIgnoreChoice.NO
    gitignore_paths: tuple[str, ...] = ()
    skills_directory: str = DEFAULT_SKILLS_DIRECTORY
    doc_files: tuple[str, ...] = DEFAULT_DOC_FILES
    docs_folders: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.app_name.strip():
            raise ConfigurationError("The application name must not be empty.")
        if not self.description.strip():
            raise ConfigurationError("The application description must not be empty.")

        if not isinstance(self.mode, GenerationMode):
            raise ConfigurationError(f"Unsupported generation mode: {self.mode}")
        if self.mode is GenerationMode.CUSTOM and not self.custom_rules:
            raise ConfigurationError("Custom mode requires at least one custom rule.")

        if not self.roles:
            raise ConfigurationError("Select at least one role.")
        for role in self.roles:
            if not isinstance(role, Role):
                raise ConfigurationError(f"Unsupported role: {role}")

        if not self.doc_files:
            raise ConfigurationError("At least one documentation file is required.")
        for doc_file in self.doc_files:
            ensure_safe_relative_path(doc_file, "Documentation file")

        seen_folders = set()
        for folder in self.docs_folders:
            normalized = ensure_safe_relative_path(folder, "Documentation folder")
            if normalized in self.doc_files:
                raise ConfigurationError(
                    f"Documentation folder conflicts with a documentation file: {folder}"
                )
            for existing in seen_folders:
                if normalized.startswith(existing + "/") or existing.startswith(normalized + "/"):
                    raise ConfigurationError(
                        f"Documentation folder overlaps with another: {folder}"
                    )
            if normalized in seen_folders:
                raise ConfigurationError(f"Duplicate documentation folder: {folder}")
            seen_folders.add(normalized)

        ensure_safe_relative_path(self.preset, "Preset")
        ensure_safe_relative_path(self.skills_directory, "Skills directory")

        selected_agents = set()
        for agent_name in self.agents:
            if agent_name in selected_agents:
                raise ConfigurationError(f"Duplicate target agent: {agent_name}")
            selected_agents.add(agent_name)
        from harness.adapters import adapter_names

        for agent_name in self.agents:
            if agent_name not in adapter_names():
                available = ", ".join(adapter_names())
                raise ConfigurationError(
                    f"Unsupported agent: {agent_name}. Available agents: {available}."
                )

        seen_skills = set()
        for skill in self.skills:
            if not skill.source.strip():
                raise ConfigurationError("Every skill requires a source.")
            if skill.name is not None:
                if not SKILL_NAME_PATTERN.match(skill.name):
                    raise ConfigurationError(
                        f"Invalid skill name: {skill.name}. "
                        "Use lowercase letters, digits, and single hyphens."
                    )
                if skill.name in seen_skills:
                    raise ConfigurationError(f"Duplicate skill: {skill.name}")
                seen_skills.add(skill.name)
            if skill.subdirectory is not None:
                ensure_safe_relative_path(skill.subdirectory, "Skill subdirectory")

        if self.gitignore is GitIgnoreChoice.CUSTOM:
            if not self.gitignore_paths:
                raise ConfigurationError(
                    "Add at least one .gitignore entry for the custom mode."
                )
            for entry in self.gitignore_paths:
                ensure_safe_gitignore_entry(entry)


def ordered_roles(roles: tuple[Role, ...] | list[Role]) -> tuple[Role, ...]:
    selected = set(roles)
    return tuple(role for role in ROLE_ORDER if role in selected)


def ensure_safe_gitignore_entry(value: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ConfigurationError("A .gitignore entry must not be empty.")
    if "\n" in text or "\r" in text:
        raise ConfigurationError(f"A .gitignore entry must be a single line: {value!r}")
    if "\\" in text:
        raise ConfigurationError(f"A .gitignore entry must use forward slashes: {value}")

    if text == "!":
        raise ConfigurationError("A .gitignore negation entry must include a pattern.")

    pattern = text[1:] if text.startswith("!") else text
    if pattern in GITIGNORE_BLOCKED_ENTRIES:
        raise ConfigurationError(f"Refusing to ignore the entire project: {value}")
    if pattern.startswith("/") or pattern.startswith("~"):
        raise ConfigurationError(f"A .gitignore entry must be relative: {value}")
    if any(part == ".." for part in PurePosixPath(pattern).parts):
        raise ConfigurationError(
            f"A .gitignore entry must stay inside the project: {value}"
        )
    return text


def ensure_safe_relative_path(value: str, label: str = "Path") -> str:
    text = (value or "").strip()
    if not text:
        raise ConfigurationError(f"{label} must not be empty.")
    if text == ".":
        raise ConfigurationError(f"{label} must be a named file, preset, or directory, not '.'.")
    if "\\" in text:
        raise ConfigurationError(f"{label} must use forward slashes: {value}")
    candidate = PurePosixPath(text)
    if candidate.is_absolute() or text.startswith("~"):
        raise ConfigurationError(f"{label} must be relative to the target directory: {value}")
    if any(part == ".." for part in candidate.parts):
        raise ConfigurationError(f"{label} must stay inside the target directory: {value}")
    return str(candidate)
