from __future__ import annotations

from harness.adapters import AgentAdapter

ADAPTER = AgentAdapter(
    name="hermes",
    display_name="Hermes",
    instructions_file=None,
    skills_directory="skills",
    notes=(
        "Hermes configuration is user-managed. Verify the instruction file and skill "
        "discovery path against your Hermes installation."
    ),
)
