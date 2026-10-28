from __future__ import annotations

from pathlib import Path

import pytest

from harness import skills
from harness.config import ConfigurationError


def write_skill(directory: Path, content: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(content, encoding="utf-8")
    return directory


def test_catalog_entries_have_required_metadata():
    catalog = skills.load_catalog()
    assert catalog
    for entry in catalog:
        assert entry.name
        assert entry.description
        assert entry.repo_url.startswith("https://")
        assert entry.license


def test_catalog_lookup_finds_known_skill():
    entry = skills.find_catalog_skill("docx")
    assert entry is not None
    assert entry.subdirectory == "skills/docx"


def test_unknown_catalog_skill_returns_none():
    assert skills.find_catalog_skill("does-not-exist") is None


def test_install_copies_skill_from_local_directory(tmp_path, skill_source):
    destination = tmp_path / "project" / "skills"
    result = skills.install_skill(str(skill_source), destination)

    assert result.name == "demo-skill"
    assert result.destination == destination / "demo-skill"
    assert result.license == "MIT"
    assert (result.destination / "SKILL.md").is_file()
    assert (result.destination / "reference.md").is_file()
    assert (result.destination / "scripts" / "helper.sh").is_file()


def test_install_excludes_repository_metadata(tmp_path, skill_source):
    destination = tmp_path / "project" / "skills"
    result = skills.install_skill(str(skill_source), destination)

    assert not (result.destination / ".git").exists()
    assert not (result.destination / ".github").exists()
    assert not (result.destination / ".gitignore").exists()


def test_install_refuses_to_overwrite_existing_skill(tmp_path, skill_source):
    destination = tmp_path / "project" / "skills"
    result = skills.install_skill(str(skill_source), destination)
    original = (result.destination / "SKILL.md").read_text(encoding="utf-8")

    with pytest.raises(skills.SkillConflictError, match="already exists"):
        skills.install_skill(str(skill_source), destination)

    assert (result.destination / "SKILL.md").read_text(encoding="utf-8") == original


def test_install_uses_requested_subdirectory(tmp_path, multi_skill_repository):
    destination = tmp_path / "project" / "skills"
    result = skills.install_skill(
        str(multi_skill_repository), destination, subdirectory="skills/beta-skill"
    )
    assert result.name == "beta-skill"
    assert (result.destination / "SKILL.md").is_file()


def test_repository_with_multiple_skills_requires_subdirectory(tmp_path, multi_skill_repository):
    with pytest.raises(skills.SkillValidationError, match="Multiple skills found"):
        skills.install_skill(str(multi_skill_repository), tmp_path / "skills")


def test_missing_skill_file_is_rejected(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(skills.SkillValidationError, match="No SKILL.md"):
        skills.install_skill(str(empty), tmp_path / "skills")


def test_missing_subdirectory_is_rejected(tmp_path, skill_source):
    with pytest.raises(skills.SkillSourceError, match="Subdirectory not found"):
        skills.install_skill(
            str(skill_source), tmp_path / "skills", subdirectory="missing"
        )


@pytest.mark.parametrize(
    ("frontmatter", "message"),
    [
        ("# No frontmatter\n", "must start with YAML frontmatter"),
        ("---\nname: demo\ndescription: [unclosed\n---\n", "Invalid YAML"),
        ("---\ndescription: Missing name.\n---\n", "Invalid skill name"),
        ("---\nname: Demo Skill\ndescription: Uppercase.\n---\n", "Invalid skill name"),
        ("---\nname: demo\n---\n", "must declare a description"),
        ("---\nname: demo\ndescription:   \n---\n", "must declare a description"),
    ],
)
def test_invalid_frontmatter_is_rejected(tmp_path, frontmatter, message):
    skill = write_skill(tmp_path / "invalid-skill", frontmatter)
    with pytest.raises(skills.SkillValidationError, match=message):
        skills.install_skill(str(skill), tmp_path / "skills")


def test_unsafe_skill_name_is_rejected(tmp_path):
    skill = write_skill(
        tmp_path / "invalid-skill",
        "---\nname: ../escape\ndescription: Unsafe name.\n---\n",
    )
    with pytest.raises(skills.SkillValidationError):
        skills.install_skill(str(skill), tmp_path / "skills")


def test_unsupported_source_scheme_is_rejected(tmp_path):
    with pytest.raises(skills.SkillSourceError, match="Unsupported skill source"):
        skills.install_skill("ftp://example.com/skill", tmp_path / "skills")


def test_unsafe_subdirectory_is_rejected(tmp_path, skill_source):
    with pytest.raises(ConfigurationError):
        skills.install_skill(str(skill_source), tmp_path / "skills", subdirectory="../..")


def test_symbolic_links_are_not_copied(tmp_path, skill_source):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    link = skill_source / "linked.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symbolic links are not supported on this platform.")

    result = skills.install_skill(str(skill_source), tmp_path / "skills")
    assert not (result.destination / "linked.txt").exists()


def test_frontmatter_license_is_parsed_when_present(tmp_path):
    skill = write_skill(
        tmp_path / "licensed-skill",
        "---\nname: licensed-skill\ndescription: Licensed.\nlicense: Apache-2.0\n---\n",
    )
    metadata = skills.validate_skill_directory(skill)
    assert metadata.license == "Apache-2.0"


def test_frontmatter_without_license_is_allowed(tmp_path):
    skill = write_skill(
        tmp_path / "unlicensed-skill",
        "---\nname: unlicensed-skill\ndescription: No license.\n---\n",
    )
    result = skills.install_skill(str(skill), tmp_path / "skills")
    assert result.license is None
