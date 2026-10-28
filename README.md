# Quick Harness

A small, deterministic CLI that scaffolds a project-specific AI coding agent harness: an `AGENTS.md` instruction file, empty documentation placeholders, and reusable [Agent Skills](https://agentskills.io) installed from open-source repositories.

The generator never calls an AI API and never configures a specific agent for you. It writes files, installing skills only when you ask for them.

## Requirements

- Windows, macOS, or Linux
- Python 3.10 or newer
- Git, only when installing skills from a Git repository; local skill directories do not need Git

## Installation

Install the CLI once; `harness` is then available from any project directory.

```bash
uv tool install --editable .
```

An editable tool install keeps the global command in sync with this checkout, so source changes apply immediately. Use `uv tool install .` instead for a fixed copy of the current code.

Run `uv tool update-shell` if `harness` is not found after installation. This configures the tool directory for your current platform. Remove the command with:

```bash
uv tool uninstall quick-harness
```

Without `uv`, a user-level install works from a Python with `pip`:

```bash
pip install --user .
```

On Windows, run the same command in PowerShell or Command Prompt. If `harness` is not found afterward, add Python's user scripts directory to `PATH` or use `uv tool install`.

To install from the checked-out source with Python instead of `uv`, run:

```bash
python -m pip install .
```

After installation, start the interactive project setup with:

```bash
harness init
```

To see all available commands:

```bash
harness --help
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

`init` collects the application name and description, the generation mode, the project roles, the target agents, optional custom rules, additional documentation folders, skills, and how `.gitignore` should be handled. It then shows a preview and waits for confirmation before writing anything.

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
  --docs-folder screenshots \
  --docs-folder guides \
  --skill test-driven-development \
  --gitignore default
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
│   ├── workflow.md
│   └── screenshots/         # optional additional folder
│       └── .gitkeep
└── skills/                  # or the skills directory of the selected agent
    └── <skill-name>/
        └── SKILL.md
```

Documentation files are intentionally created empty. No agent-specific configuration is generated.

### Documentation folders

`--docs-folder` (repeatable) adds extra folders inside `docs/` for material such as screenshots, guides, assets, or API references. The interactive flow offers `screenshots`, `guides`, `assets`, and `api`, and accepts custom folder names. Each folder receives an empty `.gitkeep` file so it survives in Git; without a tracked file, Git would drop the empty directory.

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

`init` asks how to handle `.gitignore`:

| Mode | Behavior |
| --- | --- |
| `no` | Leave `.gitignore` untouched. This is the default, since shared instructions are useful to teammates. |
| `default` | Add the generated harness paths: `AGENTS.md`, `docs/`, and the skills directory. |
| `custom` | Choose which generated paths to ignore and add any entries you want, such as `.env` or `node_modules/`. |

Custom entries are passed with repeatable flags:

```bash
harness init . --yes --name "Acme Shop" --description "An online storefront" \
  --gitignore custom \
  --gitignore-path "AGENTS.md" \
  --gitignore-path ".env" \
  --gitignore-path "node_modules/"
```

Existing `.gitignore` content is always preserved, duplicate entries are not added, and only the requested entries are written. Entries must be relative single-line patterns: absolute paths, `..`, backslashes, and project-wide patterns such as `*` or `/**` are rejected so the repository cannot be ignored wholesale.

## Development

The global tool install excludes test dependencies. Create a project environment and install the development dependencies:

```bash
python -m venv .venv
```

Activate it with the command for your shell:

```bash
source .venv/bin/activate
```

```powershell
.venv\Scripts\Activate.ps1
```

Then install and run the suite using the environment's Python:

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

The suite covers configuration validation, deterministic rendering, generation and overwrite protection, `.gitignore` handling, skill validation and installation, and the CLI commands. Skills tests use local temporary directories, so they never touch the network.
