"""Gemini API 呼び出し（ストリーミング）。"""

from google import genai
from google.genai import types

# 品質ごとに使うモデル（使えないモデルがあればここを書き換えてください）
QUALITY = {
    "速さ優先": "gemini-3.1-flash-lite",
    "標準": "gemini-3.5-flash",
    "高品質": "gemini-3.1-pro-preview",
}

BLOCKED = {
    types.FinishReason.SAFETY,
    types.FinishReason.PROHIBITED_CONTENT,
    types.FinishReason.BLOCKLIST,
    types.FinishReason.SPII,
}


class RefusalError(Exception):
    pass


def stream_text(client: genai.Client, system: str, user: str, model: str):
    """生成されたテキストを少しずつ yield するジェネレーター。"""
    finish_reason = None
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=user,
        config=types.GenerateContentConfig(system_instruction=system),
    ):
        if chunk.prompt_feedback and chunk.prompt_feedback.block_reason:
            raise RefusalError("この依頼は生成できませんでした。内容を変えてもう一度お試しください。")
        if chunk.candidates and chunk.candidates[0].finish_reason:
            finish_reason = chunk.candidates[0].finish_reason
        if chunk.text:
            yield chunk.text

    if finish_reason in BLOCKED:
        raise RefusalError("安全性フィルターにより生成が止まりました。内容を変えてもう一度お試しください。")
    if finish_reason == types.FinishReason.MAX_TOKENS:
        yield "\n\n（※ 出力が長すぎたため途中で終了しました）"
