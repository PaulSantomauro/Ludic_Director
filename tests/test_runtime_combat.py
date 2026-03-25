from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from ludic_director import (
    DirectorConfig,
    GameDirectorHooks,
    OpenAIToolClient,
    Soul,
    run_combat_loop,
)


@dataclass
class FakeView:
    running: bool = True
    ai_paused: bool = False
    ai_step_requested: bool = False
    action_queue: queue.Queue = field(default_factory=queue.Queue)
    world_event: threading.Event = field(default_factory=threading.Event)
    state: dict[str, Any] = field(default_factory=lambda: {"current_wave": 1})
    ticks: int = 0

    def get_summary(self) -> dict[str, Any]:
        self.ticks += 1
        return {"tick": self.ticks, "enemies_alive": 0, "current_wave": 1}

    def get_rich_summary(self) -> dict[str, Any]:
        return {
            **self.get_summary(),
            "game_tension": {"stress_level": "relaxed", "threat_level": "low", "health_ratio": 1.0, "player_power": {}},
            "available_content": {"enemy_types": ["Goblin"], "pending_sprite_types": []},
        }

    def touch_layer_activity(self, layer: str) -> None:
        pass


def test_combat_rule_based_enqueues(tmp_path: Any) -> None:
    soul_path = tmp_path / "s.md"
    soul_path.write_text("## I\n", encoding="utf-8")
    soul = Soul(str(soul_path))
    view = FakeView()
    cfg = DirectorConfig(backend="rule_based", combat_interval=0.01)
    client = OpenAIToolClient(log_event=None)
    hooks = GameDirectorHooks(
        build_combat_prompt=lambda s, p, c, sl: "x",
        build_world_prompt=lambda s, p, sl, m: "x",
        build_player_prompt=lambda *a, **k: "x",
        claim_player_milestone=lambda g: None,
        world_gate=lambda g, t, w: "skip",
        rule_based_combat=lambda g: {"name": "noop", "args": {}},
    )
    log_path = str(tmp_path / "l.jsonl")

    t = threading.Thread(
        target=run_combat_loop,
        args=(view, soul, lambda: cfg, lambda: [{"name": "noop", "description": "d", "parameters": {"type": "object"}}], frozenset({"noop"}), client, hooks),
        kwargs={"log_path": log_path},
        daemon=True,
    )
    t.start()
    time.sleep(0.08)
    view.running = False
    t.join(timeout=2.0)
    assert not view.action_queue.empty()
