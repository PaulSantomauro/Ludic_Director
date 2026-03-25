from pathlib import Path

from ludic_director.jsonlog import append_jsonl, read_recent_jsonl


def test_append_and_read_jsonl(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    append_jsonl(str(log), {"a": 1})
    append_jsonl(str(log), {"b": 2})
    rows = read_recent_jsonl(str(log), max_entries=10)
    assert rows == [{"a": 1}, {"b": 2}]


def test_read_recent_truncates(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    for i in range(5):
        append_jsonl(str(log), {"i": i})
    rows = read_recent_jsonl(str(log), max_entries=2)
    assert rows == [{"i": 3}, {"i": 4}]
