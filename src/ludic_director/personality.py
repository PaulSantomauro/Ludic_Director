from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Personality:
    """Lightweight mood / traits adjusted from high-level game_state hints."""

    personality_traits: dict[str, float] = field(
        default_factory=lambda: {
            "creativity": 0.8,
            "aggression": 0.6,
            "experimentation": 0.8,
            "player_empathy": 0.4,
        }
    )
    mood: str = "curious"

    def adapt_to_situation(self, game_state: dict[str, Any]) -> None:
        tension = game_state.get("game_tension") or {}
        stress = tension.get("stress_level", "relaxed")
        if stress == "critical":
            self.personality_traits["aggression"] = max(0.0, self.personality_traits["aggression"] - 0.2)
            self.personality_traits["player_empathy"] = min(1.0, self.personality_traits["player_empathy"] + 0.2)
            self.mood = "protective"
        elif stress == "relaxed":
            self.personality_traits["creativity"] = min(1.0, self.personality_traits["creativity"] + 0.05)
            self.mood = "experimental"
        else:
            self.mood = "analytical"

    def get_personality_prompt(self) -> str:
        return (
            f"Mood={self.mood}, creativity={self.personality_traits['creativity']:.2f}, "
            f"aggression={self.personality_traits['aggression']:.2f}"
        )
