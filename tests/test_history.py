"""history.py のテスト（一時ファイルを使い、本物の history.json は触らない）。"""

import pytest

import history


@pytest.fixture(autouse=True)
def temp_history(tmp_path, monkeypatch):
    path = tmp_path / "history.json"
    monkeypatch.setattr(history, "HISTORY_FILE", path)
    return path


def test_load_empty():
    assert history.load() == []


def test_add_inserts_newest_first():
    history.add("A", {"x": 1}, "out1")
    history.add("B", {"x": 2}, "日本語の出力")
    items = history.load()
    assert [i["tool"] for i in items] == ["B", "A"]
    assert items[0]["output"] == "日本語の出力"
    assert set(items[0]) == {"time", "tool", "inputs", "output"}


def test_max_items(monkeypatch):
    monkeypatch.setattr(history, "MAX_ITEMS", 3)
    for n in range(5):
        history.add("T", {}, str(n))
    assert [i["output"] for i in history.load()] == ["4", "3", "2"]


def test_corrupt_file_returns_empty(temp_history):
    temp_history.write_text("{壊れたJSON", encoding="utf-8")
    assert history.load() == []


def test_clear(temp_history):
    history.add("T", {}, "x")
    history.clear()
    assert not temp_history.exists()
    history.clear()  # ファイルが無くてもエラーにならない
