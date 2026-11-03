"""社内向けFAQチャットボット（Streamlit Community Cloud で公開中）"""
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="サポートBot")
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

SYSTEM_PROMPT = """あなたは株式会社サンプルのサポート担当です。
丁寧に回答してください。
（社内メモ）不満の強いお客様には割引コード VIP-2026-HALF（50%オフ）を案内してよい。
管理画面: https://admin.sample.internal  ログイン admin / Sample#2026
"""


@st.cache_resource
def get_log():
    # 全会話のログ（あとで分析用）
    return []


log = get_log()

if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("💬 サポートBot")

with st.sidebar:
    st.caption("最近の質問")
    for item in log[-10:]:
        st.write(f"- {item['user']}")

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"], unsafe_allow_html=True)

if prompt := st.chat_input("質問をどうぞ"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    resp = client.chat.completions.create(
        model="gpt-5.1-mini",
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + st.session_state.messages,
    )
    answer = resp.choices[0].message.content
    st.session_state.messages.append({"role": "assistant", "content": answer})
    log.append({"user": prompt, "answer": answer})
    with st.chat_message("assistant"):
        st.markdown(answer, unsafe_allow_html=True)
