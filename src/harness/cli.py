from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from harness import generator, prompts
from harness.config import ConfigurationError, GITIGNORE_ENTRIES, HarnessConfig
from harness.generator import GenerationError

APP_HELP = "Create a personal agent workspace for a project."
console = Console()
app = typer.Typer(add_completion=False, no_args_is_help=True, help=APP_HELP)


@app.callback()
def main_callback() -> None:
    """Personal agent workspace tools."""


@app.command("init")
def init_command(
    target: Path = typer.Argument(Path("."), help="Target project directory."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show planned files without writing them."
    ),
    name: Optional[str] = typer.Option(None, "--name", help="Project title."),
    description: Optional[str] = typer.Option(None, "--description", help="Project description."),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Run without prompts. Requires --name and --description."
    ),
) -> None:
    try:
        root = _prepare_root(target)
        config = _config_from_options(name, description) if yes else prompts.collect_harness_config(root)
        plan = generator.build_plan(config, root)
        _print_preview(plan)

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
        elif not yes and not prompts.ask_confirm("Write the workspace files?", default=True):
            console.print("Cancelled; no files were written.")
            return

        result = generator.apply_plan(plan, allow_overwrite=overwrite)
        _print_result(result)
    except prompts.PromptCancelled:
        console.print("Cancelled; no files were written.")
    except (ConfigurationError, GenerationError) as error:
        _fail(str(error))


def _config_from_options(name: Optional[str], description: Optional[str]) -> HarnessConfig:
    if not name or not name.strip() or not description or not description.strip():
        raise ConfigurationError("--name and --description are required when running with --yes.")
    config = HarnessConfig(app_name=name.strip(), description=description.strip())
    config.validate()
    return config


def _prepare_root(target: Path) -> Path:
    root = target.expanduser()
    if root.exists() and not root.is_dir():
        raise ConfigurationError(f"Target is not a directory: {root}")
    return root.resolve()


def _print_preview(plan: generator.GenerationPlan) -> None:
    console.print()
    console.print(f"[bold]Target:[/bold] {plan.target_root}")
    table = Table(title="Planned files", header_style="bold")
    table.add_column("Status")
    table.add_column("Path")
    table.add_column("Kind")
    for planned in plan.files:
        status = "[yellow]overwrite[/yellow]" if planned.relative_path in plan.conflicts else "[green]create[/green]"
        table.add_row(status, planned.relative_path, planned.kind)
    console.print(table)
    if plan.docs_skipped:
        console.print("Existing docs/ detected; documentation folders will be left untouched.")
    console.print("[bold].gitignore entries:[/bold] " + ", ".join(GITIGNORE_ENTRIES))


def _print_result(result: generator.GenerationResult) -> None:
    console.print()
    console.print(
        f"Generated [bold]{len(result.written_files)}[/bold] file(s) in {result.target_root}."
    )
    if result.gitignore_added:
        console.print(".gitignore updated with: " + ", ".join(result.gitignore_added))
    console.print("Next: review AGENT.md, then track work in PLAN.md and PROGRESS.md.")


def _fail(message: str) -> None:
    console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
