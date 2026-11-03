"""prompts.py のテスト（API は呼ばない）。"""

import re
from pathlib import Path

import pytest

import prompts

# app.py のフォームが作るのと同じキーを持つサンプル入力
SAMPLE_INPUTS = {
    "📝 ブログ記事": {"theme": "家庭菜園", "audience": "", "keywords": "", "length": 2000,
                    "tone": prompts.TONES[0], "notes": ""},
    "✉️ メール返信": {"received": "来週の打ち合わせの件", "intent": "", "relation": "取引先",
                    "tone": prompts.TONES[0], "sender": ""},
    "📄 要約": {"text": "本文", "style": next(iter(prompts.SUMMARY_STYLES))},
    "✏️ 校正・リライト": {"text": "本文", "mode": next(iter(prompts.REWRITE_MODES))},
    "📱 SNS投稿": {"topic": "新記事公開", "platform": next(iter(prompts.SNS_PLATFORMS)),
                  "tone": prompts.TONES[0], "count": 3},
    "🌐 翻訳": {"text": "こんにちは", "target": "英語"},
    "💡 タイトル・キャッチコピー": {"topic": "新商品", "kind": prompts.COPY_KINDS[0], "audience": "",
                              "count": 10, "tone": prompts.TONES[0]},
    "💬 自由リクエスト": {"request": "退職のあいさつ文"},
}

FREE_TOOL = "💬 自由リクエスト"  # app.py では else 節で処理される


def test_sample_inputs_cover_all_tools():
    assert set(SAMPLE_INPUTS) == set(prompts.TOOLS)


@pytest.mark.parametrize("label", list(prompts.TOOLS))
def test_builder_returns_system_and_user(label):
    system, user = prompts.TOOLS[label](SAMPLE_INPUTS[label])
    assert isinstance(system, str) and system.strip()
    assert isinstance(user, str) and user.strip()


@pytest.mark.parametrize("style", list(prompts.SUMMARY_STYLES))
def test_every_summary_style(style):
    _, user = prompts.summarize({"text": "本文", "style": style})
    assert prompts.SUMMARY_STYLES[style] in user


@pytest.mark.parametrize("mode", list(prompts.REWRITE_MODES))
def test_every_rewrite_mode(mode):
    _, user = prompts.rewrite({"text": "本文", "mode": mode})
    assert prompts.REWRITE_MODES[mode] in user


@pytest.mark.parametrize("platform", list(prompts.SNS_PLATFORMS))
def test_every_sns_platform(platform):
    _, user = prompts.sns({"topic": "x", "platform": platform, "tone": "ていねい", "count": 1})
    assert prompts.SNS_PLATFORMS[platform] in user


def test_empty_optional_fields_get_defaults():
    _, user = prompts.blog(SAMPLE_INPUTS["📝 ブログ記事"])
    assert "一般読者" in user and "特になし" in user


def test_app_form_has_branch_for_every_tool():
    """TOOLS のラベルと app.py の `tool == "..."` 分岐が一致しているか。"""
    source = (Path(__file__).parent.parent / "app.py").read_text(encoding="utf-8")
    branches = set(re.findall(r'tool == "([^"]+)"', source))
    expected = set(prompts.TOOLS) - {FREE_TOOL}
    assert branches == expected
