"""Minimal host: `RuntimeView`, rule-based combat, threaded `run_director_session`."""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from ludic_director import (
    DirectorConfig,
    DirectorPaths,
    GameDirectorHooks,
    Memory,
    OpenAIToolClient,
    Soul,
    WorldLoopState,
    run_director_session,
)


@dataclass
class FakeGame:
    running: bool = True
    ai_paused: bool = False
    ai_step_requested: bool = False
    action_queue: queue.Queue = field(default_factory=queue.Queue)
    world_event: threading.Event = field(default_factory=threading.Event)
    state: dict[str, Any] = field(default_factory=lambda: {"current_wave": 1})

    def get_summary(self) -> dict[str, Any]:
        return {"tick": 0, "enemies_alive": 1, "current_wave": 1, "player_health": 100, "player_gold": 0, "score": 0}

    def get_rich_summary(self) -> dict[str, Any]:
        return {
            **self.get_summary(),
            "game_tension": {
                "stress_level": "relaxed",
                "threat_level": "low",
                "health_ratio": 1.0,
                "player_power": {"recommended_spawn_range": (3, 8), "wave_scale": "small"},
            },
            "available_content": {"enemy_types": ["Demo"], "pending_sprite_types": []},
        }

    def touch_layer_activity(self, layer: str) -> None:
        pass


def main() -> None:
    import tempfile

    tmp = tempfile.mkdtemp()
    soul_path = f"{tmp}/soul.md"
    mem_path = f"{tmp}/mem.md"
    log_path = f"{tmp}/log.jsonl"
    open(soul_path, "w", encoding="utf-8").write("# Demo soul\n")
    open(mem_path, "w", encoding="utf-8").write("# Memory\n\n(empty)\n")

    paths = DirectorPaths(soul_md=soul_path, memory_md=mem_path, memory_log_jsonl=log_path)
    soul = Soul(soul_path)
    memory = Memory(mem_path, log_path)
    game = FakeGame()
    client = OpenAIToolClient()

    def get_cfg() -> DirectorConfig:
        return DirectorConfig(backend="rule_based", combat_interval=0.2, world_interval=60.0, player_check_interval=60.0)

    noop_tool = [{"name": "noop", "description": "No-op", "parameters": {"type": "object", "properties": {}}}]

    hooks = GameDirectorHooks(
        build_combat_prompt=lambda s, p, c, sl: "You are a test director.",
        build_world_prompt=lambda s, p, sl, m: "world",
        build_player_prompt=lambda *a, **k: "player",
        claim_player_milestone=lambda g: None,
        world_gate=lambda g, t, w: "skip_world",
        rule_based_combat=lambda g: {"name": "noop", "args": {}},
    )

    combat_names = frozenset({"noop"})
    world_names = frozenset({"w"})
    player_names = frozenset({"p"})

    t = threading.Thread(
        target=lambda: run_director_session(
            game,
            paths,
            get_cfg,
            lambda: noop_tool,
            combat_names,
            world_names,
            player_names,
            client,
            hooks,
            soul=soul,
            memory=memory,
            world_state=WorldLoopState(),
        ),
        daemon=True,
    )
    t.start()
    time.sleep(0.6)
    game.running = False
    t.join(timeout=3.0)
    print("queued actions:", game.action_queue.qsize())


if __name__ == "__main__":
    main()
