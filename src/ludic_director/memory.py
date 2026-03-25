from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from typing import Any

from ludic_director.jsonlog import append_jsonl

_SAVE_MEMORY_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save the memory consolidation result to persistent storage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "history_entry": {
                        "type": "string",
                        "description": (
                            "A paragraph (2-5 sentences) summarising key events/decisions/observations. "
                            "Start with [YYYY-MM-DD HH:MM]. Include details useful for future sessions."
                        ),
                    },
                    "memory_update": {
                        "type": "string",
                        "description": (
                            "Full updated long-term memory as markdown. Include all existing facts plus "
                            "new ones. Return unchanged if nothing new."
                        ),
                    },
                },
                "required": ["history_entry", "memory_update"],
            },
        },
    }
]


class Memory:
    """
    Long-term markdown plus append-only JSONL history.
    Consolidation calls an OpenAI-compatible client when openai extra is installed.
    """

    def __init__(
        self,
        memory_path: str,
        log_path: str,
        *,
        empty_placeholder_substrings: tuple[str, ...] = (
            "(No sessions recorded yet.)",
            "(no sessions recorded yet.)",
        ),
    ) -> None:
        self.memory_path = memory_path
        self.log_path = log_path
        self._empty_markers = empty_placeholder_substrings

    def read_long_term(self) -> str:
        try:
            with open(self.memory_path, encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            return ""

    def write_long_term(self, content: str) -> None:
        parent = os.path.dirname(self.memory_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        try:
            with open(self.memory_path, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError:
            pass

    def append_history(self, entry: str) -> None:
        append_jsonl(self.log_path, entry)

    def get_context_block(self) -> str:
        lt = self.read_long_term()
        if not lt:
            return ""
        lower = lt.lower()
        if any(marker.lower() in lower for marker in self._empty_markers):
            return ""
        return f"## What you remember from previous sessions\n{lt}\n\n"

    def consolidate(
        self,
        recent_events: list[dict[str, Any]],
        api_base: str | None,
        model: str,
        api_key: str | None,
        *,
        log_json: Callable[[dict[str, Any]], None] | None = None,
    ) -> bool:
        """Consolidate recent events into long-term memory via an LLM tool call."""
        if not recent_events:
            return True

        def _log(obj: dict[str, Any]) -> None:
            if log_json:
                log_json(obj)
            else:
                append_jsonl(self.log_path, obj)

        try:
            from openai import OpenAI
        except ImportError:
            _log({"event": "memory_consolidation_error", "error": "openai package not installed"})
            return False

        try:
            client = (
                OpenAI(base_url=api_base, api_key=(api_key or os.getenv("OPENAI_API_KEY", "")))
                if api_base
                else OpenAI(api_key=(api_key or os.getenv("OPENAI_API_KEY", "")))
            )
            current_memory = self.read_long_term()
            lines = [json.dumps(e) for e in recent_events[-40:]]
            prompt = (
                f"## Current Long-term Memory\n{current_memory or '(empty)'}\n\n"
                f"## Recent Game Events\n" + "\n".join(lines)
            )
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a memory consolidation agent for a game AI director. "
                            "Call save_memory with a summary of what you learned about this player "
                            "and this run, and an updated long-term memory markdown document."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                tools=_SAVE_MEMORY_TOOL,
                tool_choice="required",
                temperature=0.4,
            )
            choice = resp.choices[0]
            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                args = json.loads(choice.message.tool_calls[0].function.arguments or "{}")
                if entry := args.get("history_entry"):
                    self.append_history(
                        json.dumps({"ts": time.time(), "event": "memory_consolidation", "entry": entry})
                    )
                if update := args.get("memory_update"):
                    if update != current_memory:
                        self.write_long_term(update)
                return True
        except Exception as ex:
            _log({"event": "memory_consolidation_error", "error": str(ex)})
        return False
