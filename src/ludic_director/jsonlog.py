from __future__ import annotations

import json
import os
import threading
from collections.abc import Mapping
from typing import Any

_log_lock = threading.RLock()


def append_jsonl(path: str, obj: Mapping[str, Any] | str) -> None:
    """Append one JSON object as a single line (JSONL), or append a raw string line."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    line = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    with _log_lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line.rstrip() + "\n")


def read_recent_jsonl(path: str, max_entries: int = 60) -> list[dict[str, Any]]:
    """Return up to max_entries parsed JSON objects from the end of a JSONL file."""
    if max_entries <= 0 or not os.path.exists(path):
        return []
    lines: list[str] = []
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []
    parsed: list[dict[str, Any]] = []
    for line in lines[-max_entries:]:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                parsed.append(obj)
        except json.JSONDecodeError:
            continue
    return parsed
