from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from harness.config import (
    ConfigurationError,
    GenerationMode,
    GitIgnoreChoice,
    HarnessConfig,
    Role,
    ensure_safe_gitignore_entry,
    ensure_safe_relative_path,
    ordered_roles,
)


def test_default_configuration_is_valid(config_factory):
    config_factory().validate()


def test_empty_application_name_is_rejected(config_factory):
    config = config_factory(app_name="   ")
    with pytest.raises(ConfigurationError, match="application name"):
        config.validate()


def test_empty_description_is_rejected(config_factory):
    config = config_factory(description="")
    with pytest.raises(ConfigurationError, match="description"):
        config.validate()


def test_custom_mode_requires_custom_rules(config_factory):
    config = config_factory(mode=GenerationMode.CUSTOM)
    with pytest.raises(ConfigurationError, match="Custom mode requires"):
        config.validate()


def test_custom_mode_with_rules_is_valid(config_factory):
    config = config_factory(
        mode=GenerationMode.CUSTOM,
        custom_rules=("Keep pull requests small.",),
    )
    config.validate()


def test_custom_gitignore_requires_paths(config_factory):
    config = config_factory(gitignore=GitIgnoreChoice.CUSTOM)
    with pytest.raises(ConfigurationError, match="gitignore"):
        config.validate()


def test_unsupported_agent_is_rejected(config_factory):
    config = config_factory(agents=("unknown-agent",))
    with pytest.raises(ConfigurationError, match="Unsupported agent"):
        config.validate()


def test_unsafe_skills_directory_is_rejected(config_factory):
    config = config_factory(skills_directory="../outside")
    with pytest.raises(ConfigurationError, match="inside the target directory"):
        config.validate()


def test_duplicate_skill_names_are_rejected(config_factory):
    from harness.config import SkillSelection

    config = config_factory(
        skills=(
            SkillSelection(name="demo", source="https://example.com/one"),
            SkillSelection(name="demo", source="https://example.com/two"),
        )
    )
    with pytest.raises(ConfigurationError, match="Duplicate skill"):
        config.validate()


def test_documentation_folders_are_validated(config_factory):
    config_factory(docs_folders=("screenshots", "guides/api")).validate()


def test_unsafe_documentation_folder_is_rejected(config_factory):
    with pytest.raises(ConfigurationError, match="inside the target directory"):
        config_factory(docs_folders=("../outside",)).validate()


def test_duplicate_documentation_folder_is_rejected(config_factory):
    with pytest.raises(ConfigurationError, match="Duplicate documentation folder"):
        config_factory(docs_folders=("screenshots", "screenshots")).validate()


def test_documentation_folder_cannot_collide_with_a_documentation_file(config_factory):
    with pytest.raises(ConfigurationError, match="conflicts with a documentation file"):
        config_factory(docs_folders=("architecture.md",)).validate()


@pytest.mark.parametrize(
    "entry",
    ["*", "/*", "/**", "/dist", "~/secrets", "../escape", "line\nbreak", "dotted\\path"],
)
def test_unsafe_gitignore_entries_are_rejected(entry):
    with pytest.raises(ConfigurationError):
        ensure_safe_gitignore_entry(entry)


def test_gitignore_entries_accept_patterns():
    assert ensure_safe_gitignore_entry("node_modules/") == "node_modules/"
    assert ensure_safe_gitignore_entry(".env") == ".env"
    assert ensure_safe_gitignore_entry("!keep.log") == "!keep.log"
    assert ensure_safe_gitignore_entry("  docs  ") == "docs"


def test_ordered_roles_follow_canonical_order(config_factory):
    config = config_factory(roles=(Role.FULLSTACK, Role.FRONTEND, Role.BACKEND))
    assert ordered_roles(config.roles) == (Role.FRONTEND, Role.BACKEND, Role.FULLSTACK)


@pytest.mark.parametrize(
    "value",
    ["../escape", "/absolute/path", "~/home", "docs\\windows"],
)
def test_unsafe_relative_paths_are_rejected(value):
    with pytest.raises(ConfigurationError):
        ensure_safe_relative_path(value)


def test_safe_relative_path_is_normalized():
    assert ensure_safe_relative_path("docs/project-overview.md") == "docs/project-overview.md"


def test_configuration_is_immutable(config_factory):
    config = config_factory()
    with pytest.raises(FrozenInstanceError):
        config.app_name = "Changed"
    assert isinstance(config, HarnessConfig)
