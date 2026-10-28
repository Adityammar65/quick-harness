from __future__ import annotations

from harness.adapters import AgentAdapter

ADAPTER = AgentAdapter(
    name="claude",
    display_name="Claude Code",
    instructions_file="CLAUDE.md",
    skills_directory=".claude/skills",
    notes=(
        "Claude Code reads CLAUDE.md and discovers skills in .claude/skills. "
        "Import AGENTS.md from CLAUDE.md if you want both agents to share instructions."
    ),
)
