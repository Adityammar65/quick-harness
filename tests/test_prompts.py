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
        "Other documentation folders, comma separated, or leave empty to skip": "",
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
            [Role.FULLSTACK]
            if message == "Agent roles"
            else (["claude"] if message == "Target agents" else [])
        ),
    )

    config = prompts.collect_harness_config(tmp_path / "project")

    assert config.app_name == "Demo App"
    assert config.mode is GenerationMode.HYBRID
    assert config.roles == (Role.FULLSTACK,)
    assert config.agents == ("claude",)
    assert config.preset == "general"
    assert config.skills == ()
    assert config.docs_folders == ()
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
                "Other documentation folders, comma separated, or leave empty to skip": "",
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


def test_custom_gitignore_selection_merges_generated_and_extra_entries(monkeypatch, tmp_path):
    monkeypatch.setattr(
        prompts,
        "ask_text",
        lambda message, default="", validate=None: {
            "Application name": "Demo",
            "Application description": "Demo app.",
            "Additional rule, or leave empty to finish": "",
            "Other documentation folders, comma separated, or leave empty to skip": "",
            "Custom skill Git URL or local path, or leave empty to skip": "",
            "Skills directory": ".claude/skills",
            "Additional .gitignore entries, comma separated, or leave empty to skip": "node_modules/, .env",
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
            [Role.FRONTEND]
            if message == "Agent roles"
            else (
                ["claude"]
                if message == "Target agents"
                else (["docs/"] if message == "Generated paths to add to .gitignore" else [])
            )
        ),
    )

    config = prompts.collect_harness_config(tmp_path)

    assert config.gitignore is GitIgnoreChoice.CUSTOM
    assert config.gitignore_paths == ("docs/", "node_modules/", ".env")


def test_documentation_folders_are_collected(monkeypatch, tmp_path):
    monkeypatch.setattr(
        prompts,
        "ask_text",
        lambda message, default="", validate=None: {
            "Application name": "Demo",
            "Application description": "Demo app.",
            "Additional rule, or leave empty to finish": "",
            "Other documentation folders, comma separated, or leave empty to skip": "screenshots, guides",
            "Custom skill Git URL or local path, or leave empty to skip": "",
            "Skills directory": "skills",
        }[message],
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
            [Role.FULLSTACK]
            if message == "Agent roles"
            else (
                ["claude"]
                if message == "Target agents"
                else (["assets"] if message == "Additional documentation folders inside docs/" else [])
            )
        ),
    )

    config = prompts.collect_harness_config(tmp_path)

    assert config.docs_folders == ("assets", "screenshots", "guides")


def test_cancelled_prompt_is_raised(monkeypatch, tmp_path):
    monkeypatch.setattr(
        prompts.questionary, "text", lambda *args, **kwargs: FakeQuestion(None)
    )
    with pytest.raises(prompts.PromptCancelled):
        prompts.collect_harness_config(tmp_path)


def test_custom_mode_requires_at_least_one_rule(monkeypatch, tmp_path):
    rule_answers = iter(["", "", "Keep changes small.", ""])
    monkeypatch.setattr(
        prompts,
        "ask_text",
        lambda message, default="", validate=None: (
            next(rule_answers)
            if message.startswith("Additional rule")
            else {
                "Application name": "Demo",
                "Application description": "Demo app.",
                "Other documentation folders, comma separated, or leave empty to skip": "",
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
