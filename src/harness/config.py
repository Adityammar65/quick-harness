from __future__ import annotations

from dataclasses import dataclass

INSTRUCTION_FILE = "AGENT.md"
PLAN_FILE = "PLAN.md"
PROGRESS_FILE = "PROGRESS.md"
RECAP_FILE = "RECAP.md"
GITIGNORE_FILE = ".gitignore"
DOCS_DIRECTORY = "docs"
DEFAULT_DOCS_FOLDERS = ("screenshots", "guide", "logs")
GITIGNORE_ENTRIES = (INSTRUCTION_FILE, PLAN_FILE, PROGRESS_FILE, RECAP_FILE, "docs/logs/")


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class HarnessConfig:
    app_name: str
    description: str
    uses_docker: bool = False

    def validate(self) -> None:
        if not self.app_name.strip():
            raise ConfigurationError("The project title must not be empty.")
        if not self.description.strip():
            raise ConfigurationError("The project description must not be empty.")
