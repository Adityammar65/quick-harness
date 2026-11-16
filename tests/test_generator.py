from __future__ import annotations

import pytest

from harness import generator


def test_plan_contains_personal_files_and_docs_folders(tmp_path, config_factory):
    plan = generator.build_plan(config_factory(), tmp_path)
    assert [planned.relative_path for planned in plan.files] == [
        "AGENT.md",
        "PROGRESS.md",
        "RECAP.md",
        "docs/screenshots/.gitkeep",
        "docs/guide/.gitkeep",
        "docs/logs/.gitkeep",
    ]
    assert plan.conflicts == ()
    assert not plan.docs_existing


def test_docker_files_are_created_empty_only_when_enabled(tmp_path, config_factory):
    config = config_factory(uses_docker=True)
    plan = generator.build_plan(config, tmp_path)
    docker_paths = ("Dockerfile", "docker-compose.yml", ".dockerignore")
    assert tuple(path.relative_path for path in plan.files[3:6]) == docker_paths
    result = generator.apply_plan(plan)
    assert result.written_files[3:6] == docker_paths
    for filename in docker_paths:
        assert (tmp_path / filename).is_file()
        assert (tmp_path / filename).read_text(encoding="utf-8") == ""

    agent = (tmp_path / "AGENT.md").read_text(encoding="utf-8")
    assert "do not run Docker operations (including Compose or logs)" in agent
    assert "or tests. Ask the user to run them." in agent


def test_docker_files_and_rules_are_absent_by_default(tmp_path, config_factory):
    generator.apply_plan(generator.build_plan(config_factory(), tmp_path))
    for filename in ("Dockerfile", "docker-compose.yml", ".dockerignore"):
        assert not (tmp_path / filename).exists()
    agent = (tmp_path / "AGENT.md").read_text(encoding="utf-8")
    assert "Docker Rules" not in agent


def test_non_docker_mode_preserves_preexisting_dockerignore(tmp_path, config_factory):
    dockerignore = tmp_path / ".dockerignore"
    dockerignore.write_text("existing framework rules\n", encoding="utf-8")
    generator.apply_plan(generator.build_plan(config_factory(), tmp_path))
    assert dockerignore.read_text(encoding="utf-8") == "existing framework rules\n"


def test_agent_md_contains_supplied_title_description_and_rules(tmp_path, config_factory):
    generator.apply_plan(generator.build_plan(config_factory(), tmp_path))
    content = (tmp_path / "AGENT.md").read_text(encoding="utf-8")
    assert content.startswith("# Acme Shop\n\nAn online storefront")
    assert "Functionality first; appearance second." in content
    assert "`PROGRESS.md`" in content
    assert "in English" in content
    assert "(`YYYY-MM-DD`)" in content
    assert "At 7,000 lines" in content
    assert "docs/logs/PROGRESS-LOG-N.md" in content
    assert "Create new `PROGRESS.md` at project root folder" in content
    assert "`RECAP.md`" in content
    assert "urgent, fix, defer, or no fix" in content
    assert "Flag security risks separately with their impact and urgency" in content
    assert "only after the user says it has new findings" in content
    assert "seek approval for out-of-scope recommendations" in content
    assert "leave one blank line above and below" in content


def test_apply_plan_writes_empty_work_files_and_docs_placeholders(tmp_path, config_factory):
    result = generator.apply_plan(generator.build_plan(config_factory(), tmp_path))
    assert result.written_files[:3] == ("AGENT.md", "PROGRESS.md", "RECAP.md")
    for filename in ("PROGRESS.md", "RECAP.md"):
        assert (tmp_path / filename).read_text(encoding="utf-8") == ""
    for folder in ("screenshots", "guide", "logs"):
        placeholder = tmp_path / "docs" / folder / ".gitkeep"
        assert placeholder.is_file()
        assert placeholder.stat().st_size == 0


def test_build_plan_does_not_write_files(tmp_path, config_factory):
    generator.build_plan(config_factory(), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_existing_docs_directory_is_preserved_and_extended(tmp_path, config_factory):
    docs = tmp_path / "docs"
    docs.mkdir()
    existing = docs / "existing.md"
    existing.write_text("Keep this.\n", encoding="utf-8")
    plan = generator.build_plan(config_factory(), tmp_path)
    assert plan.docs_existing
    assert {path.relative_path for path in plan.files if path.kind == "documentation folder"} == {
        "docs/screenshots/.gitkeep",
        "docs/guide/.gitkeep",
        "docs/logs/.gitkeep",
    }
    generator.apply_plan(plan)
    assert existing.read_text(encoding="utf-8") == "Keep this.\n"
    for folder in ("screenshots", "guide", "logs"):
        assert (docs / folder / ".gitkeep").is_file()


def test_docs_path_that_is_a_file_is_rejected(tmp_path, config_factory):
    docs = tmp_path / "docs"
    docs.write_text("Existing file", encoding="utf-8")
    with pytest.raises(generator.GenerationError, match="docs/ is not a directory"):
        generator.build_plan(config_factory(), tmp_path)
    assert docs.read_text(encoding="utf-8") == "Existing file"


def test_existing_docs_placeholder_is_preserved_while_missing_ones_are_added(
    tmp_path, config_factory
):
    existing_placeholder = tmp_path / "docs" / "screenshots" / ".gitkeep"
    existing_placeholder.parent.mkdir(parents=True)
    existing_placeholder.write_text("Keep placeholder content.\n", encoding="utf-8")

    plan = generator.build_plan(config_factory(), tmp_path)
    assert "docs/screenshots/.gitkeep" not in {file.relative_path for file in plan.files}
    result = generator.apply_plan(plan)

    assert existing_placeholder.read_text(encoding="utf-8") == "Keep placeholder content.\n"
    assert "docs/screenshots/.gitkeep" not in result.written_files
    assert (tmp_path / "docs" / "guide" / ".gitkeep").is_file()
    assert (tmp_path / "docs" / "logs" / ".gitkeep").is_file()


def test_existing_files_are_protected(tmp_path, config_factory):
    (tmp_path / "AGENT.md").write_text("Existing instructions.\n", encoding="utf-8")
    plan = generator.build_plan(config_factory(), tmp_path)
    assert plan.conflicts == ("AGENT.md",)
    with pytest.raises(generator.GenerationError, match="Refusing to overwrite"):
        generator.apply_plan(plan)
    assert (tmp_path / "AGENT.md").read_text(encoding="utf-8") == "Existing instructions.\n"
    assert not (tmp_path / "docs").exists()


def test_overwrite_is_applied_when_confirmed(tmp_path, config_factory):
    (tmp_path / "AGENT.md").write_text("Existing.\n", encoding="utf-8")
    plan = generator.build_plan(config_factory(), tmp_path)
    generator.apply_plan(plan, allow_overwrite=True)
    assert "# Acme Shop" in (tmp_path / "AGENT.md").read_text(encoding="utf-8")


def test_default_gitignore_adds_work_files(tmp_path, config_factory):
    result = generator.apply_plan(generator.build_plan(config_factory(), tmp_path))
    content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert result.gitignore_added == (
        "AGENT.md", "PROGRESS.md", "RECAP.md", "docs/logs/"
    )
    for entry in result.gitignore_added:
        assert entry in content.splitlines()


def test_gitignore_preserves_existing_entries_and_comments(tmp_path, config_factory):
    (tmp_path / ".gitignore").write_text("# personal\nnode_modules/\nAGENT.md\n", encoding="utf-8")
    result = generator.apply_plan(generator.build_plan(config_factory(), tmp_path))
    content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert content.startswith("# personal\nnode_modules/\nAGENT.md\n")
    assert result.gitignore_added == ("PROGRESS.md", "RECAP.md", "docs/logs/")


def test_gitignore_appends_without_rewriting_existing_file(tmp_path, monkeypatch):
    path = tmp_path / ".gitignore"
    original = b"# keep these bytes\r\nnode_modules/"
    path.write_bytes(original)

    def fail_rewrite(*args, **kwargs):
        raise AssertionError("Existing .gitignore must be appended, not rewritten")

    monkeypatch.setattr(generator, "write_text", fail_rewrite)
    generator.apply_gitignore(tmp_path)

    updated = path.read_bytes()
    assert updated.startswith(original)
    assert updated.endswith(b"AGENT.md\nPROGRESS.md\nRECAP.md\ndocs/logs/\n")


def test_gitignore_entries_are_not_duplicated(tmp_path, config_factory):
    generator.apply_plan(generator.build_plan(config_factory(), tmp_path))
    second = generator.apply_plan(generator.build_plan(config_factory(), tmp_path), allow_overwrite=True)
    lines = (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert second.gitignore_added == ()
    for entry in ("AGENT.md", "PROGRESS.md", "RECAP.md", "docs/logs/"):
        assert lines.count(entry) == 1


def test_target_file_instead_of_directory_is_rejected(tmp_path, config_factory):
    target = tmp_path / "project.txt"
    target.write_text("not a directory\n", encoding="utf-8")
    plan = generator.build_plan(config_factory(), target)
    with pytest.raises(generator.GenerationError, match="not a directory"):
        generator.apply_plan(plan)


def test_conflict_check_uses_resolved_paths(tmp_path, config_factory):
    real_dir = tmp_path / "real_project"
    real_dir.mkdir()
    link_dir = tmp_path / "project_link"
    link_dir.symlink_to(real_dir)
    (real_dir / "AGENT.md").write_text("Existing.\n", encoding="utf-8")
    plan = generator.build_plan(config_factory(), link_dir)
    assert plan.conflicts == ("AGENT.md",)
