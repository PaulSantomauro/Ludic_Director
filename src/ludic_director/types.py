from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, TypedDict


class ActionDict(TypedDict, total=False):
    name: str
    args: dict[str, Any]


class ToolFunctionSpec(TypedDict, total=False):
    name: str
    description: str
    parameters: dict[str, Any]


class ToolOpenAIEntry(TypedDict):
    type: str
    function: ToolFunctionSpec


@dataclass
class DirectorConfig:
    """Runtime AI director settings (reload from host each tick as needed)."""

    backend: str = "rule_based"
    api_base: str | None = None
    model: str = "gpt-4o-mini"
    openai_api_key: str | None = None
    combat_interval: float = 6.0
    world_interval: float = 90.0
    player_check_interval: float = 15.0
    heartbeat_interval: float = 30.0
    max_custom_weapons: int = 3
    temperature_combat: float = 0.75
    temperature_world: float = 0.85
    temperature_player: float = 0.75

    @classmethod
    def from_mapping(cls, m: Mapping[str, Any]) -> DirectorConfig:
        return cls(
            backend=str(m.get("backend", "rule_based")),
            api_base=m.get("api_base"),
            model=str(m.get("model", "gpt-4o-mini")),
            openai_api_key=m.get("openai_api_key"),
            combat_interval=float(m.get("combat_interval", 6.0)),
            world_interval=float(m.get("world_interval", 90.0)),
            player_check_interval=float(m.get("player_check_interval", 15.0)),
            heartbeat_interval=float(m.get("heartbeat_interval", 30.0)),
            max_custom_weapons=int(m.get("max_custom_weapons", 3)),
            temperature_combat=float(m.get("temperature_combat", 0.75)),
            temperature_world=float(m.get("temperature_world", 0.85)),
            temperature_player=float(m.get("temperature_player", 0.75)),
        )


@dataclass(frozen=True)
class DirectorLayerSpec:
    """Logical layer id and which tool names it may invoke."""

    id: str
    tool_names: frozenset[str]
    interval_setting_key: str = "combat_interval"
    temperature_setting_key: str = "temperature_combat"
    wait_on_world_event: bool = False


@dataclass
class DirectorPaths:
    """Filesystem locations managed by the host."""

    soul_md: str
    memory_md: str
    memory_log_jsonl: str
