from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from typing import Any

from ludic_director.types import ActionDict


class OpenAIToolClient:
    """
    OpenAI-compatible chat completion with a single required tool call.
    `tools_schema` entries must be dicts with keys: name, description, parameters.
    """

    def __init__(
        self,
        *,
        log_event: Callable[[dict[str, Any]], None] | None = None,
        user_message: str = "Make your decision now.",
    ) -> None:
        self._log = log_event
        self._user_message = user_message

    def decide(
        self,
        *,
        tools_schema: list[dict[str, Any]],
        system_prompt: str,
        api_base: str | None,
        model: str,
        api_key: str | None,
        temperature: float = 0.75,
        layer_tag: str = "unknown",
    ) -> ActionDict | None:
        try:
            from openai import OpenAI
        except ImportError:
            if self._log:
                self._log({"ts": time.time(), "event": "ai_llm_error", "layer": layer_tag, "error": "openai not installed"})
            return None

        try:
            client = (
                OpenAI(base_url=api_base, api_key=(api_key or os.getenv("OPENAI_API_KEY", "")))
                if api_base
                else OpenAI(api_key=(api_key or os.getenv("OPENAI_API_KEY", "")))
            )
            t0 = time.time()
            tools_payload = [{"type": "function", "function": t} for t in tools_schema]
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": self._user_message},
                ],
                tools=tools_payload,
                tool_choice="required",
                temperature=temperature,
            )
            duration = time.time() - t0
            if self._log:
                self._log(
                    {
                        "ts": time.time(),
                        "event": "ai_llm_call",
                        "layer": layer_tag,
                        "model": model,
                        "base_url": api_base,
                        "duration": duration,
                    }
                )
            choice = resp.choices[0]
            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                tc = choice.message.tool_calls[0]
                args = json.loads(tc.function.arguments or "{}")
                if self._log:
                    self._log(
                        {
                            "ts": time.time(),
                            "event": "ai_llm_tool_call",
                            "layer": layer_tag,
                            "model": model,
                            "name": tc.function.name,
                            "args": args,
                        }
                    )
                return {"name": tc.function.name, "args": args}
            return None
        except Exception as ex:
            if self._log:
                self._log({"ts": time.time(), "event": "ai_llm_error", "layer": layer_tag, "error": str(ex)})
            return None
