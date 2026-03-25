from ludic_director.personality import Personality


def test_personality_adapts_critical() -> None:
    p = Personality()
    p.adapt_to_situation({"game_tension": {"stress_level": "critical"}})
    assert p.mood == "protective"
    assert p.personality_traits["player_empathy"] > 0.4
