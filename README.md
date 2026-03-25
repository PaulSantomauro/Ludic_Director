# ludic-director

Small, game-agnostic building blocks for a **layered AI director** that drives a live simulation via an **action queue** (consume actions on your main / sim thread only).

## Concepts

- **Soul**: Markdown file injected as identity preamble in prompts (`Soul`).
- **Memory**: Long-term markdown + append-only JSONL history (`Memory`).
- **Layers**: Combat / world / player loops run on threads; each produces at most one tool call per tick and enqueues `{"name": "...", "args": {...}}` for the game to validate and apply.
- **Tool client**: OpenAI-compatible chat completions with `tool_choice="required"` (`OpenAIToolClient`).

This library does **not** validate tool arguments; your game should, on the thread that mutates state.

## Install

```bash
pip install ludic-director
# LLM backends:
pip install "ludic-director[openai]"
```

From a git checkout:

```bash
pip install -e ".[dev]"
```

## Quick start

See [`examples/minimal_director/run.py`](examples/minimal_director/run.py) for a fake host that implements `RuntimeView` and runs one combat layer.

## Integrating with a real game

1. Implement `RuntimeView` (see [`ludic_director.runtime`](src/ludic_director/runtime.py)).
2. On each simulation tick, drain `action_queue` and dispatch to your tool handlers.
3. Pass prompt builders and optional `rule_based_combat` into `run_director_session`.

[Gundai](https://github.com/PaulSantomauro/Gundai) uses this package via a thin adapter and game-specific hooks.

## License

MIT
