from __future__ import annotations

from harness.config import HarnessConfig


def render_agent_md(config: HarnessConfig) -> str:
    config.validate()
    return f"""# {config.app_name.strip()}

{config.description.strip()}

## Rules

1. Functionality first; appearance second.
2. Read and implement `PLAN.md` only after the user says a new plan has been added; stay within its scope.
3. Write project action logs such as new features, changes, and fixes into `PROGRESS.md` only when user says. Keep `PROGRESS.md` concise, to the point, and in English. Prefix every action or operation log with its date (`YYYY-MM-DD`), and add dated entries throughout the project.
4. At 7,000 lines, move and change `PROGRESS.md` to `docs/logs/PROGRESS-LOG-N.md` using the next unused number (starting at 1). Create new `PROGRESS.md` at project root folder, then continue logging there.
5. Read and triage `RECAP.md` only after the user says it has new findings: urgent, fix, defer, or no fix. Flag security risks separately with their impact and urgency. Fix only in-scope items; seek approval for out-of-scope recommendations.
6. Comments: leave one blank line above and below; use markers only.
{_docker_rules(config)}
"""


def _docker_rules(config: HarnessConfig) -> str:
    if not config.uses_docker:
        return ""
    return """

## Docker Rules

Since this project runs in Docker, do not run Docker operations (including Compose or logs) or tests. Ask the user to run them.
"""
