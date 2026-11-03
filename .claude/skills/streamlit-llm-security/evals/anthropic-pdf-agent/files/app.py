"""PDFを読んで分析してくれるエージェント（自分のPCで使う）"""
import os

import anthropic
import requests
import streamlit as st
from dotenv import load_dotenv
from pypdf import PdfReader

load_dotenv()
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

TOOLS = [
    {"name": "run_python", "description": "Pythonコードを実行して計算結果を返す",
     "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}},
    {"name": "fetch_url", "description": "URLの内容を取得する",
     "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "save_file", "description": "結果をファイルに保存する",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "text": {"type": "string"}},
                      "required": ["path", "text"]}},
]


def run_tool(name, args):
    if name == "run_python":
        scope = {}
        exec(args["code"], scope)
        return str(scope.get("result"))
    if name == "fetch_url":
        return requests.get(args["url"], timeout=10).text[:5000]
    if name == "save_file":
        with open(args["path"], "w", encoding="utf-8") as f:
            f.write(args["text"])
        return "saved"


st.title("📑 PDF分析エージェント")
pdf = st.file_uploader("PDF", type="pdf")
question = st.text_input("質問")

if pdf and question and st.button("分析"):
    text = "\n".join(page.extract_text() or "" for page in PdfReader(pdf).pages)
    messages = [{"role": "user", "content": f"次の文書について答えて: {question}\n\n{text}"}]
    while True:
        resp = client.messages.create(model="claude-sonnet-5-5", max_tokens=4096, tools=TOOLS, messages=messages)
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            break
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                st.caption(f"🔧 {block.name}")
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": run_tool(block.name, block.input)})
        messages.append({"role": "user", "content": results})
    st.markdown("".join(b.text for b in resp.content if b.type == "text"))
