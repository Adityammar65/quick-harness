from __future__ import annotations

import pytest

from harness import prompts


class FakeQuestion:
    def __init__(self, answer):
        self.answer = answer

    def ask(self):
        return self.answer


def test_collect_config_asks_title_description_then_docker(monkeypatch, tmp_path):
    questions = []

    def answer(message, default="", validate=None):
        questions.append(message)
        return {"Project title": "Sample Project", "Project description": "A local app."}.get(message, "Python")

    monkeypatch.setattr(prompts, "ask_text", answer)
    docker_questions = []
    monkeypatch.setattr(
        prompts,
        "ask_confirm",
        lambda message, default=False: docker_questions.append((message, default)) or True,
    )
    config = prompts.collect_harness_config(tmp_path / "project")
    assert config.app_name == "Sample Project"
    assert config.description == "A local app."
    assert questions == ["Project title", "Project description", "Tech stack"]
    assert config.tech_stack == "Python"
    assert docker_questions == [("Does this project use Docker?", False)]
    assert config.uses_docker


def test_title_defaults_to_target_directory_name(monkeypatch, tmp_path):
    received = []

    def answer(message, default="", validate=None):
        received.append((message, default))
        return default or ("A description" if message == "Project description" else "Python")

    monkeypatch.setattr(prompts, "ask_text", answer)
    monkeypatch.setattr(prompts, "ask_confirm", lambda *args, **kwargs: False)
    prompts.collect_harness_config(tmp_path / "personal-project")
    assert received[0] == ("Project title", "personal-project")


def test_cancelling_a_prompt_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(
        prompts.questionary, "text", lambda *args, **kwargs: FakeQuestion(None)
    )
    with pytest.raises(prompts.PromptCancelled):
        prompts.collect_harness_config(tmp_path)
