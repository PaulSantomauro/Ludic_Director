from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from ludic_director.client import OpenAIToolClient
from ludic_director.jsonlog import append_jsonl, read_recent_jsonl
from ludic_director.memory import Memory
from ludic_director.personality import Personality
from ludic_director.soul import Soul
from ludic_director.types import ActionDict, DirectorConfig, DirectorPaths

HEARTBEAT_OK = "HEARTBEAT_OK"


@dataclass
class WorldLoopState:
    last_processed_wave: int = 0
    waves_since_consolidation: int = 0


@dataclass
class GameDirectorHooks:
    """Host-provided game logic; keep prompts and gates out of the generic runtime."""

    build_combat_prompt: Callable[[dict[str, Any], Personality, int, Soul], str]
    build_world_prompt: Callable[[dict[str, Any], Personality, Soul, Memory], str]
    build_player_prompt: Callable[..., str]
    claim_player_milestone: Callable[[Any], str | None]
    world_gate: Callable[[Any, bool, WorldLoopState], str | None]
    rule_based_combat: Callable[[Any], ActionDict | None] | None = None
    filter_world_tools: Callable[[list[dict[str, Any]], dict[str, Any]], list[dict[str, Any]]] | None = None
    post_world_decision: Callable[[Soul, ActionDict, int], None] | None = None
    after_world_success: Callable[[Any, Memory, DirectorConfig, WorldLoopState, str], None] | None = None
    before_player_tick: Callable[[Any], None] | None = None
    resolve_player_tools: Callable[[list[dict[str, Any]], Any, dict[str, Any]], list[dict[str, Any]]] | None = None
    enrich_player_state: Callable[[Any, dict[str, Any]], None] | None = None
    heartbeat_tick: Callable[[Any], None] | None = None
    on_session_end_sync: Callable[[Memory, Any], None] | None = None
    spawn_final_memory_consolidation: Callable[[Memory, DirectorConfig, str], None] | None = None


@runtime_checkable
class RuntimeView(Protocol):
    """Structural contract for the live game host (implement on an adapter or the game itself)."""

    running: bool
    ai_paused: bool
    ai_step_requested: bool
    action_queue: queue.Queue
    world_event: threading.Event
    state: dict[str, Any]

    def get_summary(self) -> dict[str, Any]: ...
    def get_rich_summary(self) -> dict[str, Any]: ...
    def touch_layer_activity(self, layer: str) -> None: ...


def _tools_subset(all_tools: list[dict[str, Any]], names: frozenset[str]) -> list[dict[str, Any]]:
    return [t for t in all_tools if t.get("name") in names]


def _log_decision(
    log_path: str,
    decision: ActionDict,
    state: dict[str, Any],
    personality: Personality,
    layer: str,
) -> None:
    append_jsonl(
        log_path,
        {
            "ts": time.time(),
            "event": "ai_decision",
            "layer": layer,
            "decision": decision,
            "state": state,
            "ai_mood": personality.mood,
            "ai_traits": personality.personality_traits,
        },
    )


def run_combat_loop(
    view: RuntimeView,
    soul: Soul,
    get_config: Callable[[], DirectorConfig],
    load_tools_schema: Callable[[], list[dict[str, Any]]],
    combat_tool_names: frozenset[str],
    client: OpenAIToolClient,
    hooks: GameDirectorHooks,
    *,
    log_path: str,
) -> None:
    personality = Personality()
    consecutive_spawns = 0
    view.touch_layer_activity("combat")

    while view.running:
        cfg = get_config()
        backend = str(cfg.backend).lower()
        interval = float(cfg.combat_interval)
        api_base = cfg.api_base
        model = cfg.model
        api_key = cfg.openai_api_key
        temperature = float(cfg.temperature_combat)
        combat_schema = _tools_subset(load_tools_schema(), combat_tool_names)

        if view.ai_paused:
            if view.ai_step_requested:
                view.ai_step_requested = False
            else:
                time.sleep(0.1)
                continue

        time.sleep(interval)
        view.touch_layer_activity("combat")

        try:
            if backend == "rule_based" and hooks.rule_based_combat:
                state = view.get_summary()
                decision = hooks.rule_based_combat(view)
            elif backend in ("lmstudio", "openai"):
                state = view.get_rich_summary()
                personality.adapt_to_situation(state)
                prompt = hooks.build_combat_prompt(state, personality, consecutive_spawns, soul)
                decision = client.decide(
                    tools_schema=combat_schema,
                    system_prompt=prompt,
                    api_base=api_base,
                    model=model,
                    api_key=api_key,
                    temperature=temperature,
                    layer_tag="combat",
                )
            else:
                state = view.get_summary()
                decision = None

            if decision:
                tool_name = decision.get("name", "")
                if tool_name in ("spawn_enemy", "spawn_wave"):
                    consecutive_spawns += 1
                else:
                    consecutive_spawns = 0
                view.action_queue.put(decision)
                _log_decision(log_path, decision, state, personality, "combat")
        except Exception as ex:
            append_jsonl(log_path, {"ts": time.time(), "event": "ai_error", "layer": "combat", "error": str(ex)})


def run_world_loop(
    view: RuntimeView,
    soul: Soul,
    memory: Memory,
    get_config: Callable[[], DirectorConfig],
    load_tools_schema: Callable[[], list[dict[str, Any]]],
    world_tool_names: frozenset[str],
    client: OpenAIToolClient,
    hooks: GameDirectorHooks,
    wstate: WorldLoopState,
    *,
    log_path: str,
) -> None:
    personality = Personality()
    personality.mood = "creative"
    view.touch_layer_activity("world")

    while view.running:
        cfg = get_config()
        backend = str(cfg.backend).lower()
        world_interval = float(cfg.world_interval)
        api_base = cfg.api_base
        model = cfg.model
        api_key = cfg.openai_api_key or None
        temperature = float(cfg.temperature_world)

        triggered = view.world_event.wait(timeout=world_interval)
        view.world_event.clear()

        if not view.running:
            break
        if view.ai_paused:
            continue
        if backend not in ("lmstudio", "openai"):
            continue

        view.touch_layer_activity("world")

        skip_reason = hooks.world_gate(view, triggered, wstate)
        if skip_reason is not None:
            append_jsonl(
                log_path,
                {"ts": time.time(), "event": HEARTBEAT_OK, "layer": "world", "reason": skip_reason},
            )
            continue

        current_wave = int(view.state.get("current_wave", 1))
        wstate.last_processed_wave = current_wave

        try:
            world_schema = _tools_subset(load_tools_schema(), world_tool_names)
            state = view.get_rich_summary()
            personality.adapt_to_situation(state)
            prompt = hooks.build_world_prompt(state, personality, soul, memory)
            effective_schema = world_schema
            if hooks.filter_world_tools:
                effective_schema = hooks.filter_world_tools(world_schema, state)
            decision = client.decide(
                tools_schema=effective_schema,
                system_prompt=prompt,
                api_base=api_base,
                model=model,
                api_key=api_key if api_key is not None else "",
                temperature=temperature,
                layer_tag="world",
            )
            if decision:
                view.action_queue.put(decision)
                _log_decision(log_path, decision, state, personality, "world")
                if hooks.post_world_decision:
                    try:
                        hooks.post_world_decision(soul, decision, current_wave)
                    except Exception:
                        pass
                if hooks.after_world_success:
                    hooks.after_world_success(view, memory, cfg, wstate, log_path)
        except Exception as ex:
            append_jsonl(log_path, {"ts": time.time(), "event": "ai_error", "layer": "world", "error": str(ex)})


def run_player_loop(
    view: RuntimeView,
    soul: Soul,
    memory: Memory,
    get_config: Callable[[], DirectorConfig],
    load_tools_schema: Callable[[], list[dict[str, Any]]],
    player_tool_names: frozenset[str],
    client: OpenAIToolClient,
    hooks: GameDirectorHooks,
    *,
    log_path: str,
) -> None:
    personality = Personality()
    personality.mood = "generous"
    view.touch_layer_activity("player")

    while view.running:
        cfg = get_config()
        backend = str(cfg.backend).lower()
        check_interval = float(cfg.player_check_interval)
        api_base = cfg.api_base
        model = cfg.model
        api_key = cfg.openai_api_key
        temperature = float(cfg.temperature_player)
        max_custom = int(cfg.max_custom_weapons)

        time.sleep(check_interval)

        if not view.running:
            break
        if view.ai_paused:
            continue
        if backend not in ("lmstudio", "openai"):
            continue

        view.touch_layer_activity("player")
        if hooks.before_player_tick:
            hooks.before_player_tick(view)

        milestone = hooks.claim_player_milestone(view)
        if not milestone:
            continue

        player_schema_full = _tools_subset(load_tools_schema(), player_tool_names)
        custom_count = 0
        try:
            custom_count = len(getattr(view, "custom_weapon_keys", []))
        except Exception:
            custom_count = 0

        player_schema_no_create = [t for t in player_schema_full if t.get("name") != "create_weapon_type"]
        current_wave = int(view.state.get("current_wave", 1))
        weapon_granted_this_wave = getattr(view, "_weapon_granted_wave", -1) == current_wave
        if weapon_granted_this_wave:
            schema = [t for t in player_schema_full if t.get("name") == "send_commentary"]
        elif custom_count >= max_custom:
            schema = player_schema_no_create
        else:
            schema = player_schema_full
        if hooks.resolve_player_tools:
            schema = hooks.resolve_player_tools(schema, view, view.get_rich_summary())

        try:
            state = view.get_rich_summary()
            if hooks.enrich_player_state:
                hooks.enrich_player_state(view, state)
            state.setdefault("custom_weapons_created", list(getattr(view, "custom_weapon_keys", [])))
            state.setdefault("weapon_granted_this_wave", weapon_granted_this_wave)
            personality.adapt_to_situation(state)
            prompt = hooks.build_player_prompt(
                state, personality, milestone, soul, memory, custom_count, max_custom
            )
            decision = client.decide(
                tools_schema=schema,
                system_prompt=prompt,
                api_base=api_base,
                model=model,
                api_key=api_key if api_key is not None else "",
                temperature=temperature,
                layer_tag="player",
            )
            if decision:
                view.action_queue.put(decision)
                _log_decision(log_path, decision, state, personality, "player")
        except Exception as ex:
            append_jsonl(log_path, {"ts": time.time(), "event": "ai_error", "layer": "player", "error": str(ex)})


def run_heartbeat_loop(view: RuntimeView, get_config: Callable[[], DirectorConfig], hooks: GameDirectorHooks, *, log_path: str) -> None:
    while view.running:
        cfg = get_config()
        interval = float(cfg.heartbeat_interval)
        time.sleep(interval)
        if not view.running:
            break
        if view.ai_paused:
            continue
        if hooks.heartbeat_tick:
            try:
                hooks.heartbeat_tick(view)
            except Exception as ex:
                append_jsonl(
                    log_path,
                    {"ts": time.time(), "event": "ai_error", "layer": "heartbeat", "error": str(ex)},
                )
        else:
            wave = int(view.state.get("current_wave", 1))
            append_jsonl(
                log_path,
                {"ts": time.time(), "event": HEARTBEAT_OK, "layer": "heartbeat", "wave": wave},
            )


def default_spawn_consolidation_thread(memory: Memory, cfg: DirectorConfig, log_path: str) -> None:
    """Read recent JSONL events and consolidate in a non-daemon thread (session end)."""

    def _run() -> None:
        if str(cfg.backend).lower() not in ("lmstudio", "openai"):
            return
        recent = read_recent_jsonl(log_path, max_entries=120)
        memory.consolidate(recent, cfg.api_base, cfg.model, cfg.openai_api_key)

    threading.Thread(target=_run, daemon=False).start()


def run_director_session(
    view: RuntimeView,
    paths: DirectorPaths,
    get_config: Callable[[], DirectorConfig],
    load_tools_schema: Callable[[], list[dict[str, Any]]],
    combat_tool_names: frozenset[str],
    world_tool_names: frozenset[str],
    player_tool_names: frozenset[str],
    client: OpenAIToolClient,
    hooks: GameDirectorHooks,
    *,
    soul: Soul | None = None,
    memory: Memory | None = None,
    world_state: WorldLoopState | None = None,
) -> None:
    soul = soul or Soul(paths.soul_md)
    memory = memory or Memory(paths.memory_md, paths.memory_log_jsonl)
    wstate = world_state or WorldLoopState()

    def _get_cfg() -> DirectorConfig:
        return get_config()

    log_path = paths.memory_log_jsonl

    t_world = threading.Thread(
        target=run_world_loop,
        args=(view, soul, memory, _get_cfg, load_tools_schema, world_tool_names, client, hooks, wstate),
        kwargs={"log_path": log_path},
        daemon=True,
    )
    t_player = threading.Thread(
        target=run_player_loop,
        args=(view, soul, memory, _get_cfg, load_tools_schema, player_tool_names, client, hooks),
        kwargs={"log_path": log_path},
        daemon=True,
    )
    t_hb = threading.Thread(
        target=run_heartbeat_loop,
        args=(view, _get_cfg, hooks),
        kwargs={"log_path": log_path},
        daemon=True,
    )
    t_world.start()
    t_player.start()
    t_hb.start()

    run_combat_loop(
        view,
        soul,
        _get_cfg,
        load_tools_schema,
        combat_tool_names,
        client,
        hooks,
        log_path=log_path,
    )

    if hooks.on_session_end_sync:
        try:
            hooks.on_session_end_sync(memory, view)
        except Exception:
            pass

    if hooks.spawn_final_memory_consolidation:
        try:
            hooks.spawn_final_memory_consolidation(memory, _get_cfg(), log_path)
        except Exception:
            pass
