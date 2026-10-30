from __future__ import annotations

import pytest

from harness import templates
from harness.adapters import ordered_adapters
from harness.config import GenerationMode, Role


def test_ordered_adapters_preserve_input_order():
    result = ordered_adapters(("opencode", "claude", "hermes"))
    assert [a.name for a in result] == ["opencode", "claude", "hermes"]

    result = ordered_adapters(("hermes", "claude"))
    assert [a.name for a in result] == ["hermes", "claude"]


def test_ordered_adapters_remove_duplicates():
    result = ordered_adapters(("claude", "opencode", "claude", "hermes"))
    assert [a.name for a in result] == ["claude", "opencode", "hermes"]


def test_ordered_adapters_reject_unknown():
    with pytest.raises(Exception, match="Unsupported agent"):
        ordered_adapters(("claude", "unknown"))


def test_rendering_is_deterministic(config_factory):
    config = config_factory()
    first = templates.render_agents_md(config)
    second = templates.render_agents_md(config)
    assert first == second
    assert first.endswith("\n")


def test_rendering_includes_project_information(config_factory):
    rendered = templates.render_agents_md(config_factory())
    assert "# Acme Shop" in rendered
    assert "An online storefront for test fixtures." in rendered
    assert "General Application Conventions" in rendered


def test_hybrid_mode_includes_preset_and_custom_rules(config_factory):
    rendered = templates.render_agents_md(
        config_factory(
            mode=GenerationMode.HYBRID,
            custom_rules=("Never commit directly to main.",),
        )
    )
    assert "## Custom Rules" in rendered
    assert "Never commit directly to main." in rendered
    assert "General Application Conventions" in rendered


def test_template_mode_ignores_custom_rules(config_factory):
    rendered = templates.render_agents_md(
        config_factory(
            mode=GenerationMode.TEMPLATE,
            custom_rules=("Never commit directly to main.",),
        )
    )
    assert "Never commit directly to main." not in rendered
    assert "## Custom Rules" not in rendered
    assert "General Application Conventions" in rendered


def test_custom_mode_omits_preset_conventions(config_factory):
    rendered = templates.render_agents_md(
        config_factory(
            mode=GenerationMode.CUSTOM,
            custom_rules=("Keep pull requests small.",),
        )
    )
    assert "General Application Conventions" not in rendered
    assert "Useful Commands" not in rendered
    assert "Keep pull requests small." in rendered


def test_frontend_role_only_renders_frontend_section(config_factory):
    rendered = templates.render_agents_md(config_factory(roles=(Role.FRONTEND,)))
    assert "### Frontend" in rendered
    assert "### Backend" not in rendered
    assert "### Fullstack" not in rendered


def test_frontend_and_backend_add_cross_layer_section(config_factory):
    rendered = templates.render_agents_md(
        config_factory(roles=(Role.FRONTEND, Role.BACKEND))
    )
    assert "### Frontend" in rendered
    assert "### Backend" in rendered
    assert "### Cross-Layer Integration" in rendered


def test_fullstack_role_renders_fullstack_section(config_factory):
    rendered = templates.render_agents_md(config_factory(roles=(Role.FULLSTACK,)))
    assert "### Fullstack" in rendered
    assert "### Cross-Layer Integration" not in rendered


def test_installed_skills_are_listed_with_source(config_factory):
    from harness.config import SkillSelection

    rendered = templates.render_agents_md(
        config_factory(
            skills=(
                SkillSelection(
                    name="systematic-debugging",
                    source="https://github.com/obra/superpowers",
                    subdirectory="skills/systematic-debugging",
                    license="MIT",
                ),
            )
        )
    )
    assert "`systematic-debugging`" in rendered
    assert "https://github.com/obra/superpowers" in rendered
    assert "license: MIT" in rendered


def test_documentation_folders_are_listed(config_factory):
    rendered = templates.render_agents_md(
        config_factory(docs_folders=("screenshots", "guides"))
    )
    assert "`docs/screenshots/`" in rendered
    assert "`docs/guides/`" in rendered
    assert ".gitkeep" in rendered


def test_missing_skills_message_is_rendered(config_factory):
    rendered = templates.render_agents_md(config_factory())
    assert "No skills are installed yet." in rendered


def test_unknown_preset_raises(config_factory):
    with pytest.raises(templates.TemplateError, match="Unknown preset"):
        templates.render_agents_md(config_factory(preset="missing-preset"))


def test_presets_are_discoverable():
    names = {preset.name for preset in templates.available_presets()}
    assert {"general", "laravel", "react"} <= names


def test_preset_with_non_string_description_is_rejected(tmp_path):
    preset_dir = tmp_path / "presets"
    preset_dir.mkdir()
    (preset_dir / "bad-desc.json").write_text(
        '{"title": "Bad", "description": 123, "conventions": [], "commands": []}',
        encoding="utf-8",
    )
    import harness.templates as templates_module
    original_preset_dir = templates_module.PRESET_DIRECTORY
    try:
        templates_module.PRESET_DIRECTORY = preset_dir
        with pytest.raises(templates.TemplateError, match="description must be a string"):
            templates.load_preset("bad-desc")
    finally:
        templates_module.PRESET_DIRECTORY = original_preset_dir
