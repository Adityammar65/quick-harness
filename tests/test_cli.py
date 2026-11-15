from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from harness import prompts
from harness.cli import app
from harness.config import HarnessConfig

runner = CliRunner()


def invoke(*arguments: str):
    return runner.invoke(app, list(arguments))


class FakeQuestion:
    def __init__(self, answer):
        self.answer = answer

    def ask(self):
        return self.answer


def test_init_writes_personal_workspace_with_yes(tmp_path: Path):
    result = invoke(
        "init", str(tmp_path), "--yes", "--name", "Demo", "--description", "A demo application."
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "AGENT.md").is_file()
    for filename in ("PLAN.md", "PROGRESS.md", "RECAP.md"):
        assert (tmp_path / filename).is_file()
        assert (tmp_path / filename).read_text(encoding="utf-8") == ""
    assert (tmp_path / "docs" / "screenshots" / ".gitkeep").is_file()
    assert (tmp_path / "docs" / "guide" / ".gitkeep").is_file()
    assert (tmp_path / "docs" / "logs" / ".gitkeep").is_file()
    assert "Generated" in result.output


def test_init_dry_run_writes_nothing(tmp_path: Path):
    result = invoke(
        "init", str(tmp_path), "--yes", "--dry-run", "--name", "Demo", "--description", "A demo."
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
    (tmp_path / "AGENT.md").write_text("Existing.\n", encoding="utf-8")
    result = invoke(
        "init", str(tmp_path), "--yes", "--name", "Demo", "--description", "A demo."
    )
    assert result.exit_code == 1
    assert "Refusing to overwrite" in result.output
    assert (tmp_path / "AGENT.md").read_text(encoding="utf-8") == "Existing.\n"


def test_init_preserves_and_extends_existing_docs(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    existing = docs / "custom.md"
    existing.write_text("Custom docs", encoding="utf-8")
    result = invoke(
        "init", str(tmp_path), "--yes", "--name", "Demo", "--description", "A demo."
    )
    assert result.exit_code == 0, result.output
    assert "Existing docs/ detected" in result.output
    assert existing.read_text(encoding="utf-8") == "Custom docs"
    for folder in ("screenshots", "guide", "logs"):
        assert (docs / folder / ".gitkeep").is_file()


def test_init_appends_gitignore_entries_by_default(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    result = invoke(
        "init", str(tmp_path), "--yes", "--name", "Demo", "--description", "A demo."
    )
    assert result.exit_code == 0, result.output
    content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert content.startswith("node_modules/\n")
    for entry in ("AGENT.md", "PLAN.md", "PROGRESS.md", "RECAP.md", "docs/logs/"):
        assert content.splitlines().count(entry) == 1


def test_init_interactive_flow_uses_collected_config(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        prompts,
        "collect_harness_config",
        lambda root: HarnessConfig("Demo", "A demo."),
    )
    monkeypatch.setattr(prompts, "ask_confirm", lambda *args, **kwargs: True)
    result = invoke("init", str(tmp_path))
    assert result.exit_code == 0, result.output
    assert (tmp_path / "AGENT.md").is_file()


def test_interactive_no_docker_does_not_generate_docker_files(monkeypatch, tmp_path: Path):
    text_answers = iter(("Demo", "A demo."))
    confirm_answers = iter((False, True))
    monkeypatch.setattr(
        prompts.questionary,
        "text",
        lambda *args, **kwargs: FakeQuestion(next(text_answers)),
    )
    monkeypatch.setattr(
        prompts.questionary,
        "confirm",
        lambda *args, **kwargs: FakeQuestion(next(confirm_answers)),
    )
    result = invoke("init", str(tmp_path))
    assert result.exit_code == 0, result.output
    for filename in ("Dockerfile", "docker-compose.yml", ".dockerignore"):
        assert not (tmp_path / filename).exists()


def test_interactive_docker_choice_generates_docker_files(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        prompts,
        "collect_harness_config",
        lambda root: HarnessConfig("Demo", "A demo.", uses_docker=True),
    )
    monkeypatch.setattr(prompts, "ask_confirm", lambda *args, **kwargs: True)
    result = invoke("init", str(tmp_path))
    assert result.exit_code == 0, result.output
    for filename in ("Dockerfile", "docker-compose.yml", ".dockerignore"):
        assert (tmp_path / filename).read_text(encoding="utf-8") == ""


def test_yes_mode_defaults_to_non_docker(tmp_path: Path):
    result = invoke(
        "init", str(tmp_path), "--yes", "--name", "Demo", "--description", "A demo."
    )
    assert result.exit_code == 0, result.output
    for filename in ("Dockerfile", "docker-compose.yml", ".dockerignore"):
        assert not (tmp_path / filename).exists()


def test_skills_command_is_removed():
    result = invoke("--help")
    assert result.exit_code == 0, result.output
    assert "skills" not in result.output.lower()
