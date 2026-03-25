from pathlib import Path

from ludic_director.soul import Soul


def test_soul_preamble_and_section_update(tmp_path: Path) -> None:
    p = tmp_path / "soul.md"
    p.write_text("# X\n\n## Identity\nhello\n", encoding="utf-8")
    s = Soul(str(p))
    assert "hello" in s.read()
    assert "Your Identity" in s.as_prompt_preamble()
    s.update_section("Identity", "replaced body")
    assert "replaced body" in s.read()
    assert "hello" not in Path(p).read_text(encoding="utf-8")
