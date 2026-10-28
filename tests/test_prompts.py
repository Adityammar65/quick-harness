from __future__ import annotations

import pytest

from harness import prompts
from harness.config import GenerationMode, GitIgnoreChoice, Role


class FakeQuestion:
    def __init__(self, answer):
        self.answer = answer

    def ask(self):
        return self.answer


def test_collect_harness_config_builds_hybrid_config(monkeypatch, tmp_path):
    answers = {
        "Application name": "Demo App",
        "Application description": "A demo application.",
        "Additional rule, or leave empty to finish": "",
        "Custom skill Git URL or local path, or leave empty to skip": "",
        "Skills directory": "skills",
    }
    monkeypatch.setattr(
        prompts, "ask_text", lambda message, default="", validate=None: answers[message]
    )
    monkeypatch.setattr(
        prompts,
        "ask_select",
        lambda message, choices, default=None: (
            GenerationMode.HYBRID
            if message == "Generation mode"
            else ("general" if message == "Preset" else GitIgnoreChoice.NO)
        ),
    )
    monkeypatch.setattr(
        prompts,
        "ask_checkbox",
        lambda message, choices, defaults=(): (
            [Role.FULLSTACK] if message == "Agent roles" else (["claude"] if message == "Target agents" else [])
        ),
    )

    config = prompts.collect_harness_config(tmp_path / "project")

    assert config.app_name == "Demo App"
    assert config.mode is GenerationMode.HYBRID
    assert config.roles == (Role.FULLSTACK,)
    assert config.agents == ("claude",)
    assert config.preset == "general"
    assert config.skills == ()
    assert config.gitignore is GitIgnoreChoice.NO
    assert config.skills_directory == "skills"


def test_custom_mode_keeps_asking_until_a_rule_is_provided(monkeypatch, tmp_path):
    rule_answers = iter(["", "Keep changes small.", ""])
    monkeypatch.setattr(
        prompts,
        "ask_text",
        lambda message, default="", validate=None: (
            next(rule_answers)
            if message.startswith("Additional rule")
            else {
                "Application name": "Demo",
                "Application description": "Demo app.",
                "Custom skill Git URL or local path, or leave empty to skip": "",
                "Skills directory": "skills",
            }[message]
        ),
    )
    monkeypatch.setattr(
        prompts,
        "ask_select",
        lambda message, choices, default=None: (
            GenerationMode.CUSTOM
            if message == "Generation mode"
            else GitIgnoreChoice.NO
        ),
    )
    monkeypatch.setattr(
        prompts,
        "ask_checkbox",
        lambda message, choices, defaults=(): [Role.BACKEND] if message == "Agent roles" else [],
    )

    config = prompts.collect_harness_config(tmp_path)

    assert config.mode is GenerationMode.CUSTOM
    assert config.custom_rules == ("Keep changes small.",)


def test_cancelling_a_prompt_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(
        prompts.questionary, "text", lambda *args, **kwargs: FakeQuestion(None)
    )
    with pytest.raises(prompts.PromptCancelled):
        prompts.collect_harness_config(tmp_path)


def test_parse_rule_lines_cleans_input():
    assert prompts.parse_rule_lines("- First rule\n\n* Second rule\n") == (
        "First rule",
        "Second rule",
    )
    assert prompts.parse_rule_lines("   ") == ()


def test_custom_gitignore_selection_uses_generated_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(
        prompts,
        "ask_text",
        lambda message, default="", validate=None: {
            "Application name": "Demo",
            "Application description": "Demo app.",
            "Additional rule, or leave empty to finish": "",
            "Custom skill Git URL or local path, or leave empty to skip": "",
            "Skills directory": ".claude/skills",
        }[message],
    )
    monkeypatch.setattr(
        prompts,
        "ask_select",
        lambda message, choices, default=None: (
            GenerationMode.HYBRID
            if message == "Generation mode"
            else ("general" if message == "Preset" else GitIgnoreChoice.CUSTOM)
        ),
    )
    monkeypatch.setattr(
        prompts,
        "ask_checkbox",
        lambda message, choices, defaults=(): (
            [Role.FRONTEND] if message == "Agent roles" else (
                ["claude"] if message == "Target agents" else ["docs/"]
            )
        ),
    )

    config = prompts.collect_harness_config(tmp_path)

    assert config.gitignore is GitIgnoreChoice.CUSTOM
    assert config.gitignore_paths == ("docs/",)
