from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from harness import generator, prompts, skills, templates
from harness.adapters import UnknownAgentError, resolve_skills_directory
from harness.config import (
    DEFAULT_PRESET,
    MODE_LABELS,
    ConfigurationError,
    GenerationMode,
    GitIgnoreChoice,
    HarnessConfig,
    Role,
    SkillSelection,
)

APP_HELP = "Generate an AI coding agent harness for a project."

console = Console()

app = typer.Typer(add_completion=False, no_args_is_help=True, help=APP_HELP)
skills_app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Browse and install agent skills.",
)
app.add_typer(skills_app, name="skills")

HANDLED_ERRORS = (
    ConfigurationError,
    UnknownAgentError,
    templates.TemplateError,
    generator.GenerationError,
    skills.SkillError,
    prompts.PromptCancelled,
)


@app.command("init")
def init_command(
    target: Path = typer.Argument(Path("."), help="Target project directory."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show the planned changes without writing files."
    ),
    name: Optional[str] = typer.Option(None, "--name", help="Application name."),
    description: Optional[str] = typer.Option(
        None, "--description", help="Application description and purpose."
    ),
    mode: Optional[str] = typer.Option(
        None, "--mode", help="Generation mode: template, custom, or hybrid."
    ),
    roles: Optional[List[str]] = typer.Option(
        None, "--role", help="Role to include: frontend, backend, or fullstack. Repeatable."
    ),
    agents: Optional[List[str]] = typer.Option(
        None, "--agent", help="Target agent: claude, opencode, or hermes. Repeatable."
    ),
    preset: Optional[str] = typer.Option(
        None, "--preset", help="Preset name, for example general, laravel, or react."
    ),
    custom_rules: Optional[List[str]] = typer.Option(
        None, "--custom-rule", help="Additional instruction. Repeatable."
    ),
    docs_folders: Optional[List[str]] = typer.Option(
        None,
        "--docs-folder",
        help="Additional documentation folder inside docs/, for example screenshots. Repeatable.",
    ),
    skill_names: Optional[List[str]] = typer.Option(
        None, "--skill", help="Catalog skill to install. Repeatable."
    ),
    skills_url: Optional[str] = typer.Option(
        None, "--skills-url", help="Git URL or local directory of a custom skill."
    ),
    skills_subdirectory: Optional[str] = typer.Option(
        None, "--skills-subdirectory", help="Subdirectory that contains the custom skill."
    ),
    skills_directory: Optional[str] = typer.Option(
        None, "--skills-dir", help="Directory for installed skills."
    ),
    gitignore: Optional[str] = typer.Option(
        None, "--gitignore", help="Git ignore mode: no, default, or custom."
    ),
    gitignore_paths: Optional[List[str]] = typer.Option(
        None,
        "--gitignore-path",
        help="Entry to add when using the custom git ignore mode. Repeatable.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Run without prompts. Requires --name and --description.",
    ),
) -> None:
    try:
        root = _prepare_root(target)
        if yes:
            config = _config_from_options(
                name=name,
                description=description,
                mode=mode,
                roles=roles,
                agents=agents,
                preset=preset,
                custom_rules=custom_rules,
                docs_folders=docs_folders,
                skill_names=skill_names,
                skills_url=skills_url,
                skills_subdirectory=skills_subdirectory,
                skills_directory=skills_directory,
                gitignore=gitignore,
                gitignore_paths=gitignore_paths,
            )
        else:
            config = prompts.collect_harness_config(root)

        plan = generator.build_plan(config, root)
        _print_preview(config, plan)

        if dry_run:
            console.print("\nDry run: no files were written.")
            return

        overwrite = False
        if plan.conflicts:
            if yes:
                raise ConfigurationError(
                    "Refusing to overwrite existing files with --yes: "
                    + ", ".join(plan.conflicts)
                    + ". Remove them or run interactively to confirm."
                )
            overwrite = prompts.ask_confirm(
                f"Overwrite {len(plan.conflicts)} existing file(s)?", default=False
            )
            if not overwrite:
                console.print("Cancelled; no files were written.")
                return
        elif not yes and not prompts.ask_confirm("Write the harness files?", default=True):
            console.print("Cancelled; no files were written.")
            return

        installed = _install_selected_skills(config, root)
        if installed:
            config = replace(config, skills=installed)
            plan = generator.build_plan(config, root)

        result = generator.apply_plan(plan, allow_overwrite=overwrite)
        _print_result(result)
    except HANDLED_ERRORS as error:
        _fail(str(error))


@skills_app.command("list")
def list_command() -> None:
    try:
        catalog = skills.load_catalog()
    except skills.SkillError as error:
        _fail(str(error))
        return

    table = Table(title="Built-in skill catalog", header_style="bold")
    table.add_column("Skill", no_wrap=True)
    table.add_column("Description", overflow="fold")
    table.add_column("Source", overflow="fold")
    table.add_column("License", overflow="fold")
    for entry in catalog:
        license_label = entry.license
        if not entry.license_verified:
            license_label = f"{entry.license} (unverified)"
        table.add_row(entry.name, entry.description, entry.repo_url, license_label)
    console.print(table)
    console.print(
        "\nInstall one with [bold]harness skills install <skill>[/bold]. "
        "Review external skills before use."
    )


@skills_app.command("install")
def install_command(
    skill_name: Optional[str] = typer.Argument(
        None, help="Skill name from the built-in catalog."
    ),
    url: Optional[str] = typer.Option(
        None, "--url", help="Git repository URL or local directory containing the skill."
    ),
    subdirectory: Optional[str] = typer.Option(
        None, "--subdirectory", help="Subdirectory that contains SKILL.md."
    ),
    target: Path = typer.Option(Path("."), "--target", help="Target project directory."),
    skills_directory: str = typer.Option(
        "skills", "--skills-dir", help="Directory for installed skills."
    ),
) -> None:
    try:
        root = _prepare_root(target)
        source, selected_subdirectory, declared_license = _resolve_skill_source(
            skill_name, url, subdirectory
        )
        destination_parent = generator.resolve_target_path(root, skills_directory)
        result = skills.install_skill(
            source, destination_parent, subdirectory=selected_subdirectory
        )
        console.print(
            f"Installed [bold]{result.name}[/bold] to {result.destination}"
        )
        console.print(f"Source: {result.source}")
        console.print(
            f"License: {result.license or declared_license or 'not declared by the skill'}"
        )
        console.print("Review the skill content before use; external skills are untrusted.")
    except HANDLED_ERRORS as error:
        _fail(str(error))


def _config_from_options(
    name: Optional[str],
    description: Optional[str],
    mode: Optional[str],
    roles: Optional[List[str]],
    agents: Optional[List[str]],
    preset: Optional[str],
    custom_rules: Optional[List[str]],
    docs_folders: Optional[List[str]],
    skill_names: Optional[List[str]],
    skills_url: Optional[str],
    skills_subdirectory: Optional[str],
    skills_directory: Optional[str],
    gitignore: Optional[str],
    gitignore_paths: Optional[List[str]],
) -> HarnessConfig:
    if not name or not name.strip() or not description or not description.strip():
        raise ConfigurationError(
            "--name and --description are required when running with --yes."
        )

    mode_value = _enum_value(GenerationMode, mode, "generation mode") or GenerationMode.HYBRID
    role_values = tuple(
        _enum_value(Role, value, "role") for value in (roles or [Role.FULLSTACK.value])
    )
    agent_values = tuple(agents or ())
    preset_value = preset or DEFAULT_PRESET
    templates.load_preset(preset_value)

    selections = []
    for skill_name in skill_names or []:
        entry = skills.find_catalog_skill(skill_name)
        if entry is None:
            available = ", ".join(catalog.name for catalog in skills.load_catalog())
            raise ConfigurationError(
                f"Unknown catalog skill: {skill_name}. Available skills: {available}."
            )
        selections.append(
            SkillSelection(
                name=entry.name,
                source=entry.repo_url,
                subdirectory=entry.subdirectory,
                license=entry.license,
            )
        )
    if skills_url and skills_url.strip():
        selections.append(
            SkillSelection(
                name=None,
                source=skills_url.strip(),
                subdirectory=(skills_subdirectory or "").strip() or None,
                license=None,
            )
        )

    gitignore_choice = (
        _enum_value(GitIgnoreChoice, gitignore, ".gitignore mode") or GitIgnoreChoice.NO
    )
    selected_gitignore_paths = tuple(gitignore_paths or ())
    if gitignore_choice is GitIgnoreChoice.CUSTOM and not selected_gitignore_paths:
        raise ConfigurationError(
            "--gitignore-path is required with --gitignore custom."
        )

    resolved_skills_directory = resolve_skills_directory(agent_values, skills_directory)

    return HarnessConfig(
        app_name=name.strip(),
        description=description.strip(),
        mode=mode_value,
        roles=role_values,
        agents=agent_values,
        preset=preset_value,
        custom_rules=tuple(custom_rules or ()),
        skills=tuple(selections),
        gitignore=gitignore_choice,
        gitignore_paths=selected_gitignore_paths,
        skills_directory=resolved_skills_directory,
        docs_folders=tuple(docs_folders or ()),
    )


def _resolve_skill_source(
    skill_name: Optional[str], url: Optional[str], subdirectory: Optional[str]
) -> tuple[str, str | None, str | None]:
    if skill_name and url:
        raise ConfigurationError("Provide either a catalog skill name or --url, not both.")
    if url:
        return url.strip(), (subdirectory or "").strip() or None, None
    if not skill_name:
        raise ConfigurationError(
            "Provide a catalog skill name or --url to install a skill."
        )

    entry = skills.find_catalog_skill(skill_name)
    if entry is None:
        available = ", ".join(catalog.name for catalog in skills.load_catalog())
        raise ConfigurationError(
            f"Unknown catalog skill: {skill_name}. Available skills: {available}."
        )
    selected_subdirectory = (subdirectory or "").strip() or entry.subdirectory
    return entry.repo_url, selected_subdirectory, entry.license


def _install_selected_skills(
    config: HarnessConfig, root: Path
) -> tuple[SkillSelection, ...]:
    if not config.skills:
        return ()

    destination_parent = generator.resolve_target_path(root, config.skills_directory)
    installed = []
    for selection in config.skills:
        result = skills.install_skill(
            selection.source,
            destination_parent,
            subdirectory=selection.subdirectory,
        )
        console.print(f"Installed skill [bold]{result.name}[/bold] at {result.destination}")
        installed.append(
            replace(
                selection,
                name=result.name,
                license=result.license or selection.license,
            )
        )
    return tuple(installed)


def _enum_value(enum_type, value: Optional[str], label: str):
    if value is None:
        return None
    try:
        return enum_type(value)
    except ValueError:
        options = ", ".join(item.value for item in enum_type)
        raise ConfigurationError(
            f"Unsupported {label}: {value}. Choose one of: {options}."
        ) from None


def _prepare_root(target: Path) -> Path:
    root = target.expanduser()
    if root.exists() and not root.is_dir():
        raise ConfigurationError(f"Target is not a directory: {root}")
    return root.resolve()


def _print_preview(config: HarnessConfig, plan: generator.GenerationPlan) -> None:
    console.print()
    console.print(f"[bold]Target:[/bold] {plan.target_root}")
    console.print(f"[bold]Mode:[/bold] {MODE_LABELS[config.mode]}")

    table = Table(title="Planned files", header_style="bold")
    table.add_column("Status")
    table.add_column("Path")
    table.add_column("Kind")
    for planned in plan.files:
        status = (
            "[yellow]overwrite[/yellow]"
            if planned.relative_path in plan.conflicts
            else "[green]create[/green]"
        )
        table.add_row(status, planned.relative_path, planned.kind)
    console.print(table)

    if plan.gitignore_entries:
        console.print(
            "[bold].gitignore entries to add:[/bold] "
            + ", ".join(plan.gitignore_entries)
        )
    else:
        console.print("[bold].gitignore:[/bold] no changes")

    if config.skills:
        labels = ", ".join(selection.name or selection.source for selection in config.skills)
        console.print(f"[bold]Skills to install:[/bold] {labels} in {config.skills_directory}/")


def _print_result(result: generator.GenerationResult) -> None:
    console.print()
    console.print(
        f"Generated [bold]{len(result.written_files)}[/bold] file(s) in {result.target_root}."
    )
    if result.gitignore_added:
        console.print(".gitignore updated with: " + ", ".join(result.gitignore_added))
    console.print(
        "Next: review AGENTS.md, complete the documentation files, and configure your agent."
    )


def _fail(message: str) -> None:
    console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
