# Quick Harness: Personal Use

A small local CLI that creates a personal workspace for an AI coding agent. It asks for a project title, description, and whether the project uses Docker, then creates `AGENT.md`, `PLAN.md`, `PROGRESS.md`, `RECAP.md`, and—when appropriate—documentation and Docker files.

## Requirements

- Windows, macOS, or Linux
- Python 3.10 or newer

## Installation

Install this checkout in editable mode so updates are available immediately:

```bash
uv tool install --editable .
```

Start setup in the current directory or name another target:

```bash
harness init
harness init /path/to/project
```

For scripts, pass the title and description directly:

```bash
harness init . --yes --name "Acme Shop" --description "An online storefront"
```

`--dry-run` previews planned files without writing them. Existing generated files are protected; interactive runs ask before overwriting, and `--yes` refuses to overwrite.

## Generated workspace

```text
project-root/
├── AGENT.md
├── PLAN.md
├── PROGRESS.md
├── RECAP.md
├── .gitignore
├── Dockerfile          # only if Docker is selected
├── docker-compose.yml  # only if Docker is selected
├── .dockerignore       # only if Docker is selected
└── docs/                 # only if docs/ does not already exist
    ├── screenshots/
    │   └── .gitkeep
    ├── guide/
        └── .gitkeep
    └── logs/             # ignored by Git by default
        └── .gitkeep
```

`AGENT.md` contains the project title and description, followed by these rules:

1. Functionality first; appearance second.
2. Read and implement `PLAN.md` only after the user says a new plan has been added; stay within its scope.
3. Keep `PROGRESS.md` concise, to the point, and in English. Date each action or operation entry as `YYYY-MM-DD` and keep adding entries throughout the project.
4. At 7,000 lines, copy it to `docs/logs/PROGRESS-LOG-N.md` using the next unused number, create `docs/logs/` if needed, clear `PROGRESS.md`, and continue logging.
5. Read and triage `RECAP.md` only after the user says it has new findings: urgent, fix, defer, or no fix. Flag security risks with their impact and urgency. Fix only in-scope items; seek approval for out-of-scope recommendations.
6. Leave one blank line above and below comments; use marker comments only.

If Docker is selected, `AGENT.md` says not to run Docker operations or tests and to ask the user to run them. The generator creates empty `Dockerfile`, `docker-compose.yml`, and `.dockerignore` files in the project root. The interactive prompt asks this question; `--yes` assumes the project does not use Docker.

`PLAN.md`, `PROGRESS.md`, and `RECAP.md` are empty files ready to use. If `docs/` already exists, the generator leaves it and its contents untouched. Otherwise it creates `screenshots/`, `guide/`, and `logs/` with `.gitkeep` placeholders. `docs/logs/` is ignored by Git by default for private progress archives.

The root `.gitignore` automatically receives `AGENT.md`, `PLAN.md`, `PROGRESS.md`, `RECAP.md`, and `docs/logs/`. Existing entries are preserved and duplicates are not added.

## Development

Install development dependencies and run the suite:

```bash
python -m pip install -e ".[dev]"
python -m pytest
```
