from __future__ import annotations

import pytest

from harness import generator
from harness.config import (
    ConfigurationError,
    GitIgnoreChoice,
    Role,
)


def test_plan_contains_agents_md_and_empty_docs(tmp_path, config_factory):
    plan = generator.build_plan(config_factory(), tmp_path)
    paths = [planned.relative_path for planned in plan.files]
    assert paths == [
        "AGENTS.md",
        "docs/project-overview.md",
        "docs/architecture.md",
        "docs/conventions.md",
        "docs/workflow.md",
    ]
    doc_files = [planned for planned in plan.files if planned.kind == "documentation"]
    assert all(planned.content == "" for planned in doc_files)
    assert plan.conflicts == ()
    assert plan.gitignore_entries == ()


def test_apply_plan_writes_files_and_empty_docs(tmp_path, config_factory):
    result = generator.apply_plan(generator.build_plan(config_factory(), tmp_path))
    assert result.written_files[0] == "AGENTS.md"
    assert "# Acme Shop" in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    for doc_file in config_factory().doc_files:
        assert (tmp_path / "docs" / doc_file).read_text(encoding="utf-8") == ""
        assert (tmp_path / "docs" / doc_file).stat().st_size == 0


def test_build_plan_does_not_write_files(tmp_path, config_factory):
    generator.build_plan(config_factory(), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_existing_files_are_protected(tmp_path, config_factory):
    (tmp_path / "AGENTS.md").write_text("Existing instructions.\n", encoding="utf-8")

    plan = generator.build_plan(config_factory(), tmp_path)
    assert plan.conflicts == ("AGENTS.md",)

    with pytest.raises(generator.GenerationError, match="Refusing to overwrite"):
        generator.apply_plan(plan)

    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == "Existing instructions.\n"
    assert not (tmp_path / "docs").exists()


def test_overwrite_is_applied_when_confirmed(tmp_path, config_factory):
    (tmp_path / "AGENTS.md").write_text("Existing instructions.\n", encoding="utf-8")
    plan = generator.build_plan(config_factory(), tmp_path)
    generator.apply_plan(plan, allow_overwrite=True)
    assert "# Acme Shop" in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")


def test_path_traversal_is_rejected(tmp_path, config_factory):
    with pytest.raises(ConfigurationError):
        generator.build_plan(config_factory(skills_directory="../outside"), tmp_path)


def test_gitignore_is_ignored_by_default(tmp_path, config_factory):
    generator.apply_plan(generator.build_plan(config_factory(), tmp_path))
    assert not (tmp_path / ".gitignore").exists()


def test_gitignore_yes_adds_all_generated_paths(tmp_path, config_factory):
    config = config_factory(gitignore=GitIgnoreChoice.YES)
    result = generator.apply_plan(generator.build_plan(config, tmp_path))
    content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert result.gitignore_added == ("AGENTS.md", "docs/", "skills/")
    assert "# AI agent harness" in content
    assert "skills/" in content


def test_gitignore_preserves_existing_entries(tmp_path, config_factory):
    (tmp_path / ".gitignore").write_text("node_modules/\n/dist\n", encoding="utf-8")
    config = config_factory(gitignore=GitIgnoreChoice.YES)
    generator.apply_plan(generator.build_plan(config, tmp_path))
    content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert content.startswith("node_modules/\n/dist\n")
    assert "AGENTS.md" in content.splitlines()


def test_gitignore_entries_are_not_duplicated(tmp_path, config_factory):
    config = config_factory(gitignore=GitIgnoreChoice.YES)
    plan = generator.build_plan(config, tmp_path)
    generator.apply_plan(plan)
    second = generator.apply_plan(generator.build_plan(config, tmp_path), allow_overwrite=True)
    content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert second.gitignore_added == ()
    assert content.splitlines().count("AGENTS.md") == 1


def test_gitignore_custom_adds_only_selected_paths(tmp_path, config_factory):
    config = config_factory(
        gitignore=GitIgnoreChoice.CUSTOM,
        gitignore_paths=("docs/",),
    )
    generator.apply_plan(generator.build_plan(config, tmp_path))
    lines = (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "docs/" in lines
    assert "AGENTS.md" not in lines
    assert "skills/" not in lines


def test_gitignore_rejects_unknown_path(tmp_path, config_factory):
    config = config_factory(
        gitignore=GitIgnoreChoice.CUSTOM,
        gitignore_paths=("src/",),
    )
    with pytest.raises(ConfigurationError, match="Unsupported .gitignore path"):
        generator.build_plan(config, tmp_path)


def test_generated_paths_use_the_selected_skills_directory(tmp_path, config_factory):
    config = config_factory(gitignore=GitIgnoreChoice.YES, skills_directory=".opencode/skills")
    generator.apply_plan(generator.build_plan(config, tmp_path))
    assert ".opencode/skills/" in (tmp_path / ".gitignore").read_text(encoding="utf-8")


def test_target_file_instead_of_directory_is_rejected(tmp_path, config_factory):
    target = tmp_path / "project.txt"
    target.write_text("not a directory\n", encoding="utf-8")
    plan = generator.build_plan(config_factory(), tmp_path / "project.txt")
    with pytest.raises(generator.GenerationError, match="not a directory"):
        generator.apply_plan(plan)


def test_role_selection_changes_generated_content(tmp_path, config_factory):
    generator.apply_plan(
        generator.build_plan(config_factory(roles=(Role.BACKEND,)), tmp_path)
    )
    content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "### Backend" in content
    assert "### Frontend" not in content
