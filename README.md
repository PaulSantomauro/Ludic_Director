# Ludic-Director

Small, game-agnostic building blocks for a **layered AI director** that drives a live simulation via an **action queue** (consume actions on your main / sim thread only).

**Repository:** [github.com/PaulSantomauro/Ludic_Director](https://github.com/PaulSantomauro/Ludic_Director)

## Concepts

- **Soul**: Markdown file injected as identity preamble in prompts (`Soul`).
- **Memory**: Long-term markdown + append-only JSONL history (`Memory`).
- **Layers**: Combat / world / player loops run on threads; each produces at most one tool call per tick and enqueues `{"name": "...", "args": {...}}` for the game to validate and apply.
- **Tool client**: OpenAI-compatible chat completions with `tool_choice="required"` (`OpenAIToolClient`).

This library does **not** validate tool arguments; the host game validates and applies them on the thread that owns simulation state.

## Install

```bash
pip install git+https://github.com/PaulSantomauro/Ludic_Director.git
pip install "ludic-director[openai] @ git+https://github.com/PaulSantomauro/Ludic_Director.git"
```

Append `@<branch>` or `@<tag>` to the Git URL to pin a revision.

**Local development**

```bash
pip install -e ".[dev]"
```

## Quick start

From the repository root after installing (editable or from Git):

```bash
python examples/minimal_director/run.py
```

See [`examples/minimal_director/run.py`](examples/minimal_director/run.py) for a minimal `RuntimeView` and `run_director_session` setup.

## Integrating with a real game

1. Implement `RuntimeView` (see [`ludic_director.runtime`](src/ludic_director/runtime.py)).
2. On each simulation tick, drain `action_queue` and dispatch to your tool handlers.
3. Pass prompt builders and optional `rule_based_combat` into `run_director_session`.

## License

MIT
