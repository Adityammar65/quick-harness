from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

from harness.config import SKILL_NAME_PATTERN, ensure_safe_relative_path

SKILL_FILE = "SKILL.md"
CATALOG_FILE = Path(__file__).resolve().parent / "catalog.json"
FRONTMATTER_DELIMITER = "---"
MAX_SKILL_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
CLONE_TIMEOUT_SECONDS = 180
EXCLUDED_DIRECTORIES = {".git", ".github", ".hg", ".svn"}
EXCLUDED_FILES = {".gitignore", ".gitattributes", ".gitmodules", ".DS_Store"}
ALLOWED_SOURCE_PREFIXES = ("https://", "ssh://", "git://", "git@", "file://")


class SkillError(RuntimeError):
    pass


class SkillValidationError(SkillError):
    pass


class SkillSourceError(SkillError):
    pass


class SkillConflictError(SkillError):
    pass


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str
    license: str | None


@dataclass(frozen=True)
class CatalogSkill:
    name: str
    description: str
    repo_url: str
    subdirectory: str | None
    ref: str | None
    license: str
    license_verified: bool


@dataclass(frozen=True)
class InstalledSkill:
    name: str
    destination: Path
    source: str
    license: str | None


def load_catalog() -> tuple[CatalogSkill, ...]:
    try:
        raw_entries = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SkillError(f"Could not read the skill catalog: {error}") from error
    if not isinstance(raw_entries, list):
        raise SkillError("The skill catalog must contain a list of entries.")

    entries = []
    for raw_entry in raw_entries:
        try:
            entries.append(
                CatalogSkill(
                    name=str(raw_entry["name"]),
                    description=str(raw_entry["description"]),
                    repo_url=str(raw_entry["repo_url"]),
                    subdirectory=raw_entry.get("subdirectory"),
                    ref=raw_entry.get("ref"),
                    license=str(raw_entry.get("license") or "unverified"),
                    license_verified=bool(raw_entry.get("license_verified", False)),
                )
            )
        except (KeyError, TypeError) as error:
            raise SkillError(f"Invalid skill catalog entry: {raw_entry!r}") from error
    return tuple(entries)


def find_catalog_skill(name: str) -> CatalogSkill | None:
    for entry in load_catalog():
        if entry.name == name:
            return entry
    return None


def parse_skill_frontmatter(skill_file: Path) -> SkillMetadata:
    if not skill_file.is_file():
        raise SkillValidationError(f"No {SKILL_FILE} found at {skill_file}.")
    try:
        text = skill_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise SkillValidationError(f"Could not read {skill_file}: {error}") from error

    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_DELIMITER:
        raise SkillValidationError(f"{skill_file} must start with YAML frontmatter.")
    closing_index = next(
        (index for index in range(1, len(lines)) if lines[index].strip() == FRONTMATTER_DELIMITER),
        None,
    )
    if closing_index is None:
        raise SkillValidationError(f"{skill_file} has unterminated YAML frontmatter.")

    try:
        data = yaml.safe_load("\n".join(lines[1:closing_index]))
    except yaml.YAMLError as error:
        raise SkillValidationError(f"Invalid YAML frontmatter in {skill_file}: {error}") from error
    if not isinstance(data, dict):
        raise SkillValidationError(f"{skill_file} frontmatter must be a mapping.")

    name = data.get("name")
    description = data.get("description")
    license_value = data.get("license")

    if not isinstance(name, str) or not SKILL_NAME_PATTERN.match(name):
        raise SkillValidationError(
            f"Invalid skill name in {skill_file}: {name!r}. "
            "Use lowercase letters, digits, and single hyphens."
        )
    if len(name) > MAX_SKILL_NAME_LENGTH:
        raise SkillValidationError(
            f"Skill name in {skill_file} exceeds {MAX_SKILL_NAME_LENGTH} characters."
        )
    if not isinstance(description, str) or not description.strip():
        raise SkillValidationError(f"Skill {name} must declare a description.")
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise SkillValidationError(
            f"Skill {name} description exceeds {MAX_DESCRIPTION_LENGTH} characters."
        )

    license_text = license_value.strip() if isinstance(license_value, str) else None
    return SkillMetadata(
        name=name,
        description=description.strip(),
        license=license_text or None,
    )


def validate_skill_directory(directory: Path) -> SkillMetadata:
    if not directory.is_dir():
        raise SkillValidationError(f"Skill directory not found: {directory}")
    return parse_skill_frontmatter(directory / SKILL_FILE)


def install_skill(
    source: str,
    destination_parent: Path | str,
    subdirectory: str | None = None,
    ref: str | None = None,
) -> InstalledSkill:
    source_text = (source or "").strip()
    if not source_text:
        raise SkillSourceError("A skill repository URL or local directory is required.")

    subdirectory_text = (subdirectory or "").strip()
    if subdirectory_text:
        ensure_safe_relative_path(subdirectory_text, "Skill subdirectory")

    destination_root = Path(destination_parent).expanduser()
    local_source = Path(source_text).expanduser()
    if local_source.is_dir():
        return _install_from_directory(
            local_source.resolve(), destination_root, subdirectory_text or None, source_text
        )

    _validate_git_source(source_text)
    with tempfile.TemporaryDirectory(prefix="harness-skill-") as temporary_directory:
        repository_root = Path(temporary_directory) / "repository"
        _clone_repository(source_text, repository_root, ref)
        return _install_from_directory(
            repository_root, destination_root, subdirectory_text or None, source_text
        )


def _validate_git_source(source: str) -> None:
    if not source.startswith(ALLOWED_SOURCE_PREFIXES):
        raise SkillSourceError(
            f"Unsupported skill source: {source}. "
            "Use an https, ssh, git, or file Git URL, or a local directory."
        )


def _clone_repository(source: str, target: Path, ref: str | None) -> None:
    command = ["git", "clone", "--depth", "1", "--quiet"]
    if ref:
        command.extend(["--branch", ref])
    command.extend([source, str(target)])
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=CLONE_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as error:
        raise SkillSourceError("Git is required to install skills from a repository.") from error
    except subprocess.TimeoutExpired as error:
        raise SkillSourceError(f"Timed out while cloning {source}.") from error

    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout).strip().splitlines()
        reason = details[-1] if details else "unknown error"
        raise SkillSourceError(f"Failed to clone {source}: {reason}")


def _install_from_directory(
    repository_root: Path,
    destination_parent: Path,
    subdirectory: str | None,
    source: str,
) -> InstalledSkill:
    skill_root = _resolve_skill_root(repository_root, subdirectory)
    metadata = validate_skill_directory(skill_root)

    destination_parent = destination_parent.resolve()
    destination = destination_parent / metadata.name
    if destination.exists():
        raise SkillConflictError(
            f"Skill {metadata.name} already exists at {destination}. Remove it first."
        )

    destination_parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=destination_parent, prefix=f".{metadata.name}-"))
    try:
        _copy_skill_tree(skill_root, staging)
        os.replace(staging, destination)
    except OSError as error:
        shutil.rmtree(staging, ignore_errors=True)
        raise SkillError(f"Could not install skill {metadata.name}: {error}") from error
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    return InstalledSkill(
        name=metadata.name,
        destination=destination,
        source=source,
        license=metadata.license,
    )


def _resolve_skill_root(repository_root: Path, subdirectory: str | None) -> Path:
    if not repository_root.is_dir():
        raise SkillSourceError(f"Skill source not found: {repository_root}")

    if subdirectory:
        candidate = repository_root / subdirectory
        if not candidate.is_dir():
            raise SkillSourceError(f"Subdirectory not found in source: {subdirectory}")
        if not (candidate / SKILL_FILE).is_file():
            raise SkillValidationError(
                f"No {SKILL_FILE} found in {subdirectory}. Check the subdirectory value."
            )
        return candidate

    matches = _find_skill_directories(repository_root)
    if not matches:
        raise SkillValidationError(f"No {SKILL_FILE} found in {repository_root}.")
    if len(matches) > 1:
        relative = ", ".join(
            str(match.relative_to(repository_root)) for match in matches[:5]
        )
        raise SkillValidationError(
            f"Multiple skills found ({relative}). Provide a subdirectory to select one."
        )
    return matches[0]


def _find_skill_directories(root: Path) -> list[Path]:
    matches = []
    for current, directory_names, file_names in os.walk(root, followlinks=False):
        current_path = Path(current)
        directory_names[:] = sorted(
            name
            for name in directory_names
            if name not in EXCLUDED_DIRECTORIES and not (current_path / name).is_symlink()
        )
        if SKILL_FILE in file_names:
            matches.append(current_path)
    return sorted(matches)


def _copy_skill_tree(source: Path, destination: Path) -> None:
    for current, directory_names, file_names in os.walk(source, followlinks=False):
        current_path = Path(current)
        relative = current_path.relative_to(source)
        directory_names[:] = sorted(
            name
            for name in directory_names
            if name not in EXCLUDED_DIRECTORIES and not (current_path / name).is_symlink()
        )
        target_directory = destination / relative
        target_directory.mkdir(parents=True, exist_ok=True)

        for file_name in sorted(file_names):
            if file_name in EXCLUDED_FILES:
                continue
            source_file = current_path / file_name
            if source_file.is_symlink() or not source_file.is_file():
                continue
            shutil.copy2(source_file, target_directory / file_name)
