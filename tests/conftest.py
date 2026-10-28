from __future__ import annotations

from pathlib import Path

import pytest

from harness.config import GenerationMode, HarnessConfig, Role

SKILL_DOCUMENT = """---
name: {name}
description: {description}
license: {license}
---

# {name}

Fixture skill content.
"""


@pytest.fixture
def config_factory():
    def factory(**overrides) -> HarnessConfig:
        defaults = {
            "app_name": "Acme Shop",
            "description": "An online storefront for test fixtures.",
            "mode": GenerationMode.HYBRID,
            "roles": (Role.FULLSTACK,),
            "agents": ("claude",),
            "preset": "general",
        }
        defaults.update(overrides)
        return HarnessConfig(**defaults)

    return factory


@pytest.fixture
def skill_source(tmp_path: Path) -> Path:
    source = tmp_path / "source" / "demo-skill"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        SKILL_DOCUMENT.format(
            name="demo-skill",
            description="A skill used by the test suite.",
            license="MIT",
        ),
        encoding="utf-8",
    )
    (source / "reference.md").write_text("Reference notes.\n", encoding="utf-8")
    (source / "scripts").mkdir()
    (source / "scripts" / "helper.sh").write_text("echo helper\n", encoding="utf-8")
    (source / ".gitignore").write_text("*.log\n", encoding="utf-8")
    (source / ".git").mkdir()
    (source / ".git" / "config").write_text("", encoding="utf-8")
    (source / ".github").mkdir()
    (source / ".github" / "workflow.yml").write_text("name: ci\n", encoding="utf-8")
    return source


@pytest.fixture
def multi_skill_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    for name in ("alpha-skill", "beta-skill"):
        skill = repository / "skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            SKILL_DOCUMENT.format(
                name=name,
                description=f"The {name} fixture.",
                license="MIT",
            ),
            encoding="utf-8",
        )
    return repository
