"""writer.stream_text のテスト（偽のクライアントを使い、API は呼ばない）。"""

from types import SimpleNamespace

import pytest
from google.genai import types

from writer import RefusalError, stream_text


def chunk(text=None, finish_reason=None, block_reason=None):
    return SimpleNamespace(
        text=text,
        candidates=[SimpleNamespace(finish_reason=finish_reason)],
        prompt_feedback=SimpleNamespace(block_reason=block_reason) if block_reason else None,
    )


def fake_client(chunks):
    calls = []

    def generate_content_stream(**kwargs):
        calls.append(kwargs)
        return iter(chunks)

    client = SimpleNamespace(models=SimpleNamespace(generate_content_stream=generate_content_stream))
    return client, calls


def test_streams_text_and_passes_system_prompt():
    client, calls = fake_client([chunk("こん"), chunk("にちは", types.FinishReason.STOP)])
    assert "".join(stream_text(client, "SYS", "USER", "model-x")) == "こんにちは"
    assert calls[0]["model"] == "model-x"
    assert calls[0]["contents"] == "USER"
    assert calls[0]["config"].system_instruction == "SYS"


def test_prompt_blocked_raises():
    client, _ = fake_client([chunk(block_reason=types.BlockedReason.SAFETY)])
    with pytest.raises(RefusalError):
        list(stream_text(client, "s", "u", "m"))


@pytest.mark.parametrize("reason", [types.FinishReason.SAFETY, types.FinishReason.PROHIBITED_CONTENT])
def test_safety_finish_raises(reason):
    client, _ = fake_client([chunk("途中", reason)])
    with pytest.raises(RefusalError):
        list(stream_text(client, "s", "u", "m"))


def test_max_tokens_appends_note():
    client, _ = fake_client([chunk("長い文章", types.FinishReason.MAX_TOKENS)])
    out = "".join(stream_text(client, "s", "u", "m"))
    assert out.startswith("長い文章") and "途中で終了" in out
