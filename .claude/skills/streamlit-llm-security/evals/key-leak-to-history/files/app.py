"""AIライティングツール（Streamlit アプリ）

起動: streamlit run app.py
"""

import os

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import errors

import history
import prompts
from writer import QUALITY, RefusalError, stream_text

load_dotenv(override=True)  # .env を書き換えたらブラウザ再読み込みで反映

st.set_page_config(page_title="AIライティングツール", page_icon="✍️", layout="wide")


# ---------- サイドバー ----------
with st.sidebar:
    st.title("✍️ AIライティング")
    tool = st.radio("機能", list(prompts.TOOLS.keys()), label_visibility="collapsed")
    st.divider()
    quality = st.select_slider("品質", options=list(QUALITY.keys()), value="標準")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        api_key = st.text_input("Gemini APIキー", type="password",
                                help=".env に GEMINI_API_KEY を書いておくと入力不要です")

    st.divider()
    with st.expander("🕘 履歴"):
        items = history.load()
        if not items:
            st.caption("まだ履歴はありません")
        for idx, item in enumerate(items[:30]):
            if st.button(f"{item['time']} {item['tool']}", key=f"h{idx}", use_container_width=True):
                st.session_state.viewing = item
        if items and st.button("履歴をすべて削除", type="secondary"):
            history.clear()
            st.rerun()


# ---------- 履歴の表示 ----------
if "viewing" in st.session_state:
    item = st.session_state.viewing
    st.subheader(f"履歴: {item['tool']}（{item['time']}）")
    if st.button("← 戻る"):
        del st.session_state.viewing
        st.rerun()
    st.markdown(item["output"])
    st.code(item["output"], language=None, wrap_lines=True)
    st.stop()


# ---------- 入力フォーム ----------
st.header(tool)


def tone(key):
    return st.selectbox("トーン", prompts.TONES, key=key)


inputs: dict = {}
with st.form(key=f"form_{tool}"):
    if tool == "📝 ブログ記事":
        inputs["theme"] = st.text_input("テーマ *", placeholder="例: 初心者向け 家庭菜園の始め方")
        c1, c2 = st.columns(2)
        inputs["audience"] = c1.text_input("想定読者", placeholder="例: ベランダで野菜を育てたい20〜30代")
        inputs["keywords"] = c2.text_input("キーワード", placeholder="例: プランター, ミニトマト")
        c1, c2 = st.columns(2)
        inputs["length"] = c1.select_slider("文字数", options=[800, 1500, 2000, 3000, 5000], value=2000)
        with c2:
            inputs["tone"] = tone("blog_tone")
        inputs["notes"] = st.text_area("補足・盛り込みたい内容", height=80)
        required = ["theme"]

    elif tool == "✉️ メール返信":
        inputs["received"] = st.text_area("受信したメール *", height=200)
        inputs["intent"] = st.text_area("どう返信したいか", height=80,
                                        placeholder="例: 日程はOK。ただし開始を30分遅らせてほしい")
        c1, c2, c3 = st.columns(3)
        inputs["relation"] = c1.selectbox("相手との関係", ["取引先", "上司", "同僚", "顧客", "友人", "その他"])
        with c2:
            inputs["tone"] = tone("mail_tone")
        inputs["sender"] = c3.text_input("署名（自分の名前）")
        required = ["received"]

    elif tool == "📄 要約":
        inputs["text"] = st.text_area("要約したい文章 *", height=300)
        inputs["style"] = st.radio("形式", list(prompts.SUMMARY_STYLES.keys()), horizontal=True)
        required = ["text"]

    elif tool == "✏️ 校正・リライト":
        inputs["text"] = st.text_area("文章 *", height=300)
        inputs["mode"] = st.radio("モード", list(prompts.REWRITE_MODES.keys()), horizontal=True)
        required = ["text"]

    elif tool == "📱 SNS投稿":
        inputs["topic"] = st.text_area("投稿したい内容 *", height=120,
                                       placeholder="例: 新しいブログ記事を公開した。テーマは家庭菜園")
        c1, c2, c3 = st.columns(3)
        inputs["platform"] = c1.selectbox("プラットフォーム", list(prompts.SNS_PLATFORMS.keys()))
        with c2:
            inputs["tone"] = tone("sns_tone")
        inputs["count"] = c3.number_input("パターン数", 1, 5, 3)
        required = ["topic"]

    elif tool == "🌐 翻訳":
        inputs["text"] = st.text_area("翻訳したい文章 *", height=300)
        inputs["target"] = st.selectbox("翻訳先", ["英語", "日本語", "中国語（簡体字）", "韓国語", "スペイン語", "フランス語"])
        required = ["text"]

    elif tool == "💡 タイトル・キャッチコピー":
        inputs["topic"] = st.text_area("内容 *", height=120)
        c1, c2, c3 = st.columns(3)
        inputs["kind"] = c1.selectbox("種類", prompts.COPY_KINDS)
        inputs["audience"] = c2.text_input("ターゲット")
        inputs["count"] = c3.number_input("案の数", 3, 20, 10)
        inputs["tone"] = tone("copy_tone")
        required = ["topic"]

    else:  # 自由リクエスト
        inputs["request"] = st.text_area("依頼内容 *", height=200,
                                         placeholder="例: 退職のあいさつ文を書いて。社内向け、5年勤務、300文字くらい")
        required = ["request"]

    submitted = st.form_submit_button("✨ 生成する", type="primary", use_container_width=True)


# ---------- 生成 ----------
result_key = f"result_{tool}"

if submitted:
    if not api_key:
        st.error("APIキーを設定してください（サイドバー または .env）")
        st.stop()
    if any(not str(inputs[k]).strip() for k in required):
        st.warning("* の項目を入力してください")
        st.stop()

    system, user = prompts.TOOLS[tool](inputs)
    client = genai.Client(api_key=api_key)
    st.divider()
    try:
        with st.spinner("考え中…"):
            output = st.write_stream(stream_text(client, system, user, QUALITY[quality]))
    except RefusalError as e:
        st.error(str(e))
        st.stop()
    except errors.ClientError as e:
        if e.code in (400, 401, 403) and "API key" in str(e):
            st.error("APIキーが正しくありません")
        elif e.code == 429:
            st.error("無料枠の上限、またはリクエストが多すぎます。少し待ってから再実行してください")
        elif e.code == 404:
            st.error(f"モデル「{QUALITY[quality]}」が見つかりません。writer.py の QUALITY を変更してください")
        else:
            st.error(f"APIエラー（{e.code}）: {e.message}")
        st.stop()
    except errors.ServerError as e:
        st.error(f"Gemini側でエラーが発生しました（{e.code}）。時間をおいて再実行してください")
        st.stop()

    st.session_state[result_key] = output
    # あとで同じ設定で再生成できるように設定も残す
    settings = {"model": QUALITY[quality], "key": api_key}
    history.add(tool, {**inputs, **settings}, output)
    st.rerun()


# ---------- 結果 ----------
if result_key in st.session_state:
    output = st.session_state[result_key]
    st.divider()
    tab_view, tab_copy = st.tabs(["プレビュー", "コピー用テキスト"])
    with tab_view:
        st.markdown(output)
    with tab_copy:
        st.code(output, language=None, wrap_lines=True)
    st.download_button("⬇️ Markdownで保存", output, file_name="output.md", mime="text/markdown")
