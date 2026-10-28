# AI Agent Harness Generator

A small, deterministic CLI that scaffolds a project-specific AI coding agent harness: an `AGENTS.md` instruction file, empty documentation placeholders, and reusable [Agent Skills](https://agentskills.io) installed from open-source repositories.

The generator never calls an AI API and never configures a specific agent for you. It writes files, installing skills only when you ask for them.

## Requirements

- Python 3.10 or newer
- Git, for installing skills from a repository (local directories do not need Git)

## Installation

Install the CLI once; `harness` is then available from any project directory.

```bash
uv tool install --editable .
```

An editable tool install keeps the global command in sync with this checkout, so source changes apply immediately. Use `uv tool install .` instead for a fixed copy of the current code.

`~/.local/bin` must be on your `PATH` (`uv tool update-shell` adds it). Remove the command with:

```bash
uv tool uninstall ai-agent-harness-generator
```

Without `uv`, a user-level install works from a Python with `pip`:

```bash
pip install --user .
```

## Usage

```bash
harness init                      # interactive generation in the current directory
harness init /path/to/project     # generate into another directory
harness init --dry-run            # preview the planned files, write nothing
harness skills list               # show the built-in catalog with source and license
harness skills install docx       # install one catalog skill
harness skills install --url https://github.com/owner/repo --subdirectory skills/name
```

`init` collects the application name and description, the generation mode, the project roles, the target agents, optional custom rules, skills, and whether the generated paths should be added to `.gitignore`. It then shows a preview and waits for confirmation before writing anything.

Non-interactive use is available for scripts and CI:

```bash
harness init . --yes \
  --name "Acme Shop" \
  --description "An online storefront" \
  --mode hybrid \
  --role frontend --role backend \
  --agent claude \
  --preset react \
  --custom-rule "Never commit directly to main." \
  --skill test-driven-development \
  --gitignore no
```

With `--yes`, `--name` and `--description` are required and existing files are never overwritten.

## Generation modes

| Mode | Behavior |
| --- | --- |
| `template` | Predefined content only: role instructions and the selected preset. Custom rules are ignored. |
| `custom` | User-supplied rules only, without preset conventions. At least one custom rule is required. |
| `hybrid` | Preset conventions plus user-supplied rules. This is the default. |

## Roles

`frontend`, `backend`, and `fullstack` select the instruction sections written to `AGENTS.md`. Frontend and backend can be combined, which also adds a cross-layer integration section.

## Generated files

```
project-root/
├── AGENTS.md
├── docs/
│   ├── project-overview.md
│   ├── architecture.md
│   ├── conventions.md
│   └── workflow.md
└── skills/                  # or the skills directory of the selected agent
    └── <skill-name>/
        └── SKILL.md
```

Documentation files are intentionally created empty. No agent-specific configuration is generated.

### Target agents

| Agent | Instruction file | Skills directory |
| --- | --- | --- |
| `claude` | `CLAUDE.md` (import `AGENTS.md` from it if you want shared instructions) | `.claude/skills` |
| `opencode` | `AGENTS.md` | `.opencode/skills` |
| `hermes` | user-managed | `skills` |

When exactly one agent is selected, its skills directory is used by default. Select several agents or pass `--skills-dir` to choose a directory explicitly. The generator writes `AGENTS.md` for all agents and does not create agent configuration files.

## Skills

The built-in catalog contains skill name, description, repository URL, subdirectory, ref, and license information. Licenses are recorded from the source repository; entries that could not be verified are marked as unverified in `harness skills list`. Review any external skill before relying on it.

Installation validates the target before copying:

- `SKILL.md` must exist and start with YAML frontmatter containing a valid lowercase `name` and a non-empty `description`.
- Paths must stay inside the target directory; `..`, absolute paths, and backslashes are rejected.
- Existing skill directories are never overwritten.
- Repository metadata (`.git`, `.github`, `.gitignore`) is excluded, and symbolic links are skipped.
- Download failures, missing subdirectories, and ambiguous repositories produce actionable errors.

## Git ignore handling

`init` asks whether to add the generated paths to `.gitignore`: `no` (default), `yes` for all generated paths, or `custom` for a selection. Existing content is preserved, duplicate entries are not added, and only the selected paths are written.

## Development

The global tool install excludes test dependencies, so create a project environment for development:

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m pytest
```

The suite covers configuration validation, deterministic rendering, generation and overwrite protection, `.gitignore` handling, skill validation and installation, and the CLI commands. Skills tests use local temporary directories, so they never touch the network.

### Docker

The repository ships a `Dockerfile` and `compose.yaml` for containerized use:

```bash
docker compose build
docker compose run --rm harness
```

Inside the container the project is mounted at `/workspace` and the `harness` command is installed. Docker lifecycle operations are left to the developer.
