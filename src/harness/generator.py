from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from harness import templates
from harness.config import (
    DOCS_DIRECTORY,
    GITIGNORE_FILE,
    INSTRUCTION_FILE,
    ConfigurationError,
    GitIgnoreChoice,
    HarnessConfig,
    ensure_safe_gitignore_entry,
    ensure_safe_relative_path,
)

GITIGNORE_HEADER = "# AI agent harness"
DOCUMENTATION_PLACEHOLDER = ".gitkeep"
INSTRUCTION_KIND = "instruction"
DOCUMENTATION_KIND = "documentation"


class GenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class PlannedFile:
    relative_path: str
    content: str
    kind: str


@dataclass(frozen=True)
class GenerationPlan:
    target_root: Path
    files: tuple[PlannedFile, ...]
    gitignore_entries: tuple[str, ...]
    conflicts: tuple[str, ...]


@dataclass(frozen=True)
class GenerationResult:
    target_root: Path
    written_files: tuple[str, ...]
    gitignore_added: tuple[str, ...]


def build_plan(config: HarnessConfig, target_root: Path | str) -> GenerationPlan:
    config.validate()
    root = Path(target_root).expanduser().resolve()
    files = [PlannedFile(INSTRUCTION_FILE, templates.render_agents_md(config), INSTRUCTION_KIND)]
    files.extend(
        PlannedFile(f"{DOCS_DIRECTORY}/{doc_file}", "", DOCUMENTATION_KIND)
        for doc_file in config.doc_files
    )
    files.extend(
        PlannedFile(
            f"{DOCS_DIRECTORY}/{folder}/{DOCUMENTATION_PLACEHOLDER}",
            "",
            DOCUMENTATION_KIND,
        )
        for folder in config.docs_folders
    )
    conflicts = tuple(file.relative_path for file in files if (root / file.relative_path).exists())
    return GenerationPlan(
        target_root=root,
        files=tuple(files),
        gitignore_entries=resolve_gitignore_entries(config),
        conflicts=conflicts,
    )


def apply_plan(plan: GenerationPlan, allow_overwrite: bool = False) -> GenerationResult:
    root = plan.target_root
    if root.exists() and not root.is_dir():
        raise GenerationError(f"Target is not a directory: {root}")

    conflicts = [file.relative_path for file in plan.files if (root / file.relative_path).exists()]
    if conflicts and not allow_overwrite:
        raise GenerationError(
            "Refusing to overwrite existing files: "
            + ", ".join(conflicts)
            + ". Remove them or confirm overwriting."
        )

    root.mkdir(parents=True, exist_ok=True)
    written_files = []
    for planned in plan.files:
        destination = resolve_target_path(root, planned.relative_path)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise GenerationError(
                f"Could not create {planned.relative_path}: {error}"
            ) from error
        write_text(destination, planned.content)
        written_files.append(planned.relative_path)

    gitignore_added = apply_gitignore(root, plan.gitignore_entries)
    return GenerationResult(root, tuple(written_files), gitignore_added)


def resolve_target_path(root: Path, relative_path: str) -> Path:
    ensure_safe_relative_path(relative_path)
    resolved_root = root.resolve()
    candidate = (resolved_root / relative_path).resolve()
    if resolved_root not in candidate.parents:
        raise GenerationError(f"Refusing to write outside the target directory: {relative_path}")
    return candidate


def generated_paths(config: HarnessConfig) -> tuple[str, ...]:
    skills_path = f"{config.skills_directory.strip('/')}/"
    return (INSTRUCTION_FILE, f"{DOCS_DIRECTORY}/", skills_path)


def resolve_gitignore_entries(config: HarnessConfig) -> tuple[str, ...]:
    if config.gitignore is GitIgnoreChoice.NO:
        return ()
    if config.gitignore is GitIgnoreChoice.DEFAULT:
        return generated_paths(config)

    entries = []
    seen = set()
    for entry in config.gitignore_paths:
        normalized = ensure_safe_gitignore_entry(entry)
        key = normalized.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        entries.append(normalized)
    if not entries:
        raise ConfigurationError("Add at least one .gitignore entry for the custom mode.")
    return tuple(entries)


def apply_gitignore(root: Path, entries: tuple[str, ...]) -> tuple[str, ...]:
    if not entries:
        return ()

    path = root / GITIGNORE_FILE
    existing_text = ""
    if path.exists():
        try:
            existing_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise GenerationError(f"Could not read {path}: {error}") from error

    existing_entries = {
        line.strip().rstrip("/") for line in existing_text.splitlines() if line.strip()
    }
    added = tuple(entry for entry in entries if entry.rstrip("/") not in existing_entries)
    if not added:
        return ()

    block = [GITIGNORE_HEADER, *added]
    new_text = existing_text
    if new_text and not new_text.endswith("\n"):
        new_text += "\n"
    if new_text.strip():
        new_text += "\n"
    new_text += "\n".join(block) + "\n"

    write_text(path, new_text)
    return added


def write_text(path: Path, text: str) -> None:
    handle, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temporary_name, path)
    except OSError as error:
        Path(temporary_name).unlink(missing_ok=True)
        raise GenerationError(f"Could not write {path}: {error}") from error
