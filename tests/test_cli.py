from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from harness import skills
from harness.cli import app

runner = CliRunner()


def invoke(*arguments: str):
    return runner.invoke(app, list(arguments))


def test_init_writes_harness_with_yes(tmp_path: Path):
    result = invoke(
        "init",
        str(tmp_path),
        "--yes",
        "--name",
        "Demo",
        "--description",
        "A demo application.",
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "AGENTS.md").is_file()
    assert (tmp_path / "docs" / "architecture.md").read_text(encoding="utf-8") == ""
    assert "Generated" in result.output


def test_init_dry_run_writes_nothing(tmp_path: Path):
    result = invoke(
        "init",
        str(tmp_path),
        "--yes",
        "--dry-run",
        "--name",
        "Demo",
        "--description",
        "A demo application.",
    )
    assert result.exit_code == 0, result.output
    assert "Dry run" in result.output
    assert list(tmp_path.iterdir()) == []


def test_init_yes_requires_name_and_description(tmp_path: Path):
    result = invoke("init", str(tmp_path), "--yes")
    assert result.exit_code == 1
    assert "--name and --description are required" in result.output
    assert list(tmp_path.iterdir()) == []


def test_init_refuses_to_overwrite_with_yes(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("Existing.\n", encoding="utf-8")
    result = invoke(
        "init",
        str(tmp_path),
        "--yes",
        "--name",
        "Demo",
        "--description",
        "A demo application.",
    )
    assert result.exit_code == 1
    assert "Refusing to overwrite" in result.output
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == "Existing.\n"


def test_init_custom_mode_requires_rules(tmp_path: Path):
    result = invoke(
        "init",
        str(tmp_path),
        "--yes",
        "--mode",
        "custom",
        "--name",
        "Demo",
        "--description",
        "A demo application.",
    )
    assert result.exit_code == 1
    assert "Custom mode requires" in result.output


def test_init_rejects_unknown_role(tmp_path: Path):
    result = invoke(
        "init",
        str(tmp_path),
        "--yes",
        "--role",
        "designer",
        "--name",
        "Demo",
        "--description",
        "A demo application.",
    )
    assert result.exit_code == 1
    assert "Unsupported role" in result.output


def test_init_applies_gitignore_choice(tmp_path: Path):
    result = invoke(
        "init",
        str(tmp_path),
        "--yes",
        "--name",
        "Demo",
        "--description",
        "A demo application.",
        "--agent",
        "opencode",
        "--gitignore",
        "default",
    )
    assert result.exit_code == 0, result.output
    content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "AGENTS.md" in content
    assert ".opencode/skills/" in content


def test_init_creates_requested_documentation_folders(tmp_path: Path):
    result = invoke(
        "init",
        str(tmp_path),
        "--yes",
        "--name",
        "Demo",
        "--description",
        "A demo application.",
        "--docs-folder",
        "screenshots",
        "--docs-folder",
        "guides/api",
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "docs" / "screenshots" / ".gitkeep").is_file()
    assert (tmp_path / "docs" / "guides" / "api" / ".gitkeep").is_file()
    content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "`docs/screenshots/`" in content
    assert "`docs/guides/api/`" in content


def test_init_custom_gitignore_accepts_arbitrary_entries(tmp_path: Path):
    result = invoke(
        "init",
        str(tmp_path),
        "--yes",
        "--name",
        "Demo",
        "--description",
        "A demo application.",
        "--gitignore",
        "custom",
        "--gitignore-path",
        "AGENTS.md",
        "--gitignore-path",
        ".env",
        "--gitignore-path",
        "node_modules/",
    )
    assert result.exit_code == 0, result.output
    lines = (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "AGENTS.md" in lines
    assert ".env" in lines
    assert "node_modules/" in lines
    assert "docs/" not in lines


def test_init_rejects_project_wide_gitignore_entry(tmp_path: Path):
    result = invoke(
        "init",
        str(tmp_path),
        "--yes",
        "--name",
        "Demo",
        "--description",
        "A demo application.",
        "--gitignore",
        "custom",
        "--gitignore-path",
        "*",
    )
    assert result.exit_code == 1
    assert "Refusing to ignore the entire project" in result.output
    assert list(tmp_path.iterdir()) == []


def test_init_installs_skill_from_local_directory(tmp_path: Path, skill_source: Path):
    result = invoke(
        "init",
        str(tmp_path),
        "--yes",
        "--name",
        "Demo",
        "--description",
        "A demo application.",
        "--agent",
        "claude",
        "--skills-url",
        str(skill_source),
    )
    assert result.exit_code == 0, result.output
    installed = tmp_path / ".claude" / "skills" / "demo-skill" / "SKILL.md"
    assert installed.is_file()
    assert "demo-skill" in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")


def test_skills_list_shows_catalog():
    result = invoke("skills", "list")
    assert result.exit_code == 0, result.output
    assert "test-driven-development" in result.output
    assert "MIT" in result.output


def test_skills_install_from_local_directory(tmp_path: Path, skill_source: Path):
    result = invoke(
        "skills",
        "install",
        "--url",
        str(skill_source),
        "--target",
        str(tmp_path),
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "skills" / "demo-skill" / "SKILL.md").is_file()


def test_skills_install_requires_a_source(tmp_path: Path):
    result = invoke("skills", "install", "--target", str(tmp_path))
    assert result.exit_code == 1
    assert "Provide a catalog skill name or --url" in result.output


def test_skills_install_rejects_unknown_catalog_skill(tmp_path: Path):
    result = invoke(
        "skills",
        "install",
        "not-a-skill",
        "--target",
        str(tmp_path),
    )
    assert result.exit_code == 1
    assert "Unknown catalog skill" in result.output


def test_init_rejects_unknown_catalog_skill(tmp_path: Path):
    result = invoke(
        "init",
        str(tmp_path),
        "--yes",
        "--name",
        "Demo",
        "--description",
        "A demo application.",
        "--skill",
        "not-a-skill",
    )
    assert result.exit_code == 1
    assert "Unknown catalog skill" in result.output
    assert list(tmp_path.iterdir()) == []


def test_skills_list_handles_catalog_error(monkeypatch, tmp_path):
    def failing_catalog():
        raise skills.SkillError("Catalog unavailable")

    import harness.cli as cli_module
    import harness.skills as skills_module
    monkeypatch.setattr(cli_module.skills, "load_catalog", failing_catalog)
    monkeypatch.setattr(skills_module, "load_catalog", failing_catalog)

    result = invoke("skills", "list")
    assert result.exit_code == 1
    assert "Catalog unavailable" in result.output
