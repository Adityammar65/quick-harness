from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from harness import templates
from harness.config import (
    DEFAULT_DOCS_FOLDERS,
    DOCS_DIRECTORY,
    GITIGNORE_ENTRIES,
    GITIGNORE_FILE,
    HarnessConfig,
    ConfigurationError,
)

GITIGNORE_HEADER = "# Personal agent workspace"
DOCUMENTATION_PLACEHOLDER = ".gitkeep"
DOCKER_FILES = ("Dockerfile", "docker-compose.yml", ".dockerignore")


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
    conflicts: tuple[str, ...]
    docs_skipped: bool


@dataclass(frozen=True)
class GenerationResult:
    target_root: Path
    written_files: tuple[str, ...]
    gitignore_added: tuple[str, ...]


def build_plan(config: HarnessConfig, target_root: Path | str) -> GenerationPlan:
    config.validate()
    root = Path(target_root).expanduser().resolve()
    files = [
        PlannedFile("AGENT.md", templates.render_agent_md(config), "instructions"),
        PlannedFile("PLAN.md", "", "work log"),
        PlannedFile("PROGRESS.md", "", "work log"),
        PlannedFile("RECAP.md", "", "work log"),
    ]
    if config.uses_docker:
        files.extend(PlannedFile(path, "", "Docker") for path in DOCKER_FILES)
    docs_path = root / DOCS_DIRECTORY
    docs_skipped = docs_path.exists()
    if not docs_skipped:
        files.extend(
            PlannedFile(
                f"{DOCS_DIRECTORY}/{folder}/{DOCUMENTATION_PLACEHOLDER}",
                "",
                "documentation folder",
            )
            for folder in DEFAULT_DOCS_FOLDERS
        )

    conflicts = tuple(
        planned.relative_path
        for planned in files
        if resolve_target_path(root, planned.relative_path).exists()
    )
    return GenerationPlan(root, tuple(files), conflicts, docs_skipped)


def apply_plan(plan: GenerationPlan, allow_overwrite: bool = False) -> GenerationResult:
    root = plan.target_root
    if root.exists() and not root.is_dir():
        raise GenerationError(f"Target is not a directory: {root}")

    conflicts = [
        planned.relative_path
        for planned in plan.files
        if resolve_target_path(root, planned.relative_path).exists()
    ]
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
            raise GenerationError(f"Could not create {planned.relative_path}: {error}") from error
        write_text(destination, planned.content)
        written_files.append(planned.relative_path)

    gitignore_added = apply_gitignore(root)
    return GenerationResult(root, tuple(written_files), gitignore_added)


def resolve_target_path(root: Path, relative_path: str) -> Path:
    candidate_path = PurePosixPath(relative_path)
    if candidate_path.is_absolute() or any(part in ("", ".", "..") for part in candidate_path.parts):
        raise GenerationError(f"Refusing to write outside the target directory: {relative_path}")
    resolved_root = root.resolve()
    candidate = (resolved_root / relative_path).resolve()
    if resolved_root not in candidate.parents:
        raise GenerationError(f"Refusing to write outside the target directory: {relative_path}")
    return candidate


def apply_gitignore(root: Path) -> tuple[str, ...]:
    path = root / GITIGNORE_FILE
    existing_text = ""
    if path.exists():
        try:
            existing_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise GenerationError(f"Could not read {path}: {error}") from error

    existing_entries = {
        line.strip().rstrip("/")
        for line in existing_text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    added = tuple(entry for entry in GITIGNORE_ENTRIES if entry.rstrip("/") not in existing_entries)
    if not added:
        return ()

    new_text = existing_text
    if new_text and not new_text.endswith("\n"):
        new_text += "\n"
    if new_text.strip():
        new_text += "\n"
    new_text += "\n".join((GITIGNORE_HEADER, *added)) + "\n"
    write_text(path, new_text)
    return added


def write_text(path: Path, text: str) -> None:
    handle, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix="")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temporary_name, path)
    except OSError as error:
        Path(temporary_name).unlink(missing_ok=True)
        raise GenerationError(f"Could not write {path}: {error}") from error
