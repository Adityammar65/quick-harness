from __future__ import annotations

from harness.adapters import AgentAdapter

ADAPTER = AgentAdapter(
    name="opencode",
    display_name="OpenCode",
    instructions_file="AGENTS.md",
    skills_directory=".opencode/skills",
    notes="OpenCode reads AGENTS.md and discovers skills in .opencode/skills.",
)
