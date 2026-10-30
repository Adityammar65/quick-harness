from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentAdapter:
    name: str
    display_name: str
    instructions_file: str | None
    skills_directory: str | None
    notes: str


class UnknownAgentError(ValueError):
    pass


def all_adapters() -> tuple[AgentAdapter, ...]:
    from harness.adapters import claude, hermes, opencode

    return (claude.ADAPTER, hermes.ADAPTER, opencode.ADAPTER)


def adapter_names() -> tuple[str, ...]:
    return tuple(adapter.name for adapter in all_adapters())


def get_adapter(name: str) -> AgentAdapter:
    for adapter in all_adapters():
        if adapter.name == name:
            return adapter
    available = ", ".join(adapter_names())
    raise UnknownAgentError(f"Unsupported agent: {name}. Available agents: {available}.")


def ordered_adapters(names: tuple[str, ...] | list[str]) -> tuple[AgentAdapter, ...]:
    seen = set()
    ordered_names = []
    for name in names:
        if name not in seen:
            get_adapter(name)
            seen.add(name)
            ordered_names.append(name)
    return tuple(get_adapter(name) for name in ordered_names)


def display_names(names: tuple[str, ...] | list[str]) -> str:
    adapters = ordered_adapters(names)
    if not adapters:
        return "Not specified"
    return ", ".join(adapter.display_name for adapter in adapters)


def resolve_skills_directory(
    names: tuple[str, ...] | list[str], configured: str | None = None
) -> str:
    if configured:
        return configured
    adapters = ordered_adapters(names)
    if len(adapters) == 1 and adapters[0].skills_directory:
        return adapters[0].skills_directory
    return "skills"
