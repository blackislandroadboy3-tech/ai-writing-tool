"""Streamlit + LLM API アプリ向けの機械的なセキュリティスキャン（標準ライブラリのみ・読み取り専用）。

使い方:
    python scan.py [プロジェクトのディレクトリ]   # 省略時はカレントディレクトリ

- 秘密情報の値そのものは出力しない（先頭4文字＋伏せ字のみ）
- .env / secrets.toml は「キーが入っているか」だけを数え、値は表示しない
- 何も書き換えない
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SKIP_DIRS = {".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
             "node_modules", "site-packages", ".claude", ".agents", "dist", "build"}
TEXT_SUFFIXES = {".py", ".md", ".txt", ".toml", ".json", ".jsonl", ".yaml", ".yml", ".cfg", ".ini", ".env",
                 ".csv", ".log", ".ipynb", ".sh", ".bat", ".ps1", ""}
SECRET_FILES = {".env", "secrets.toml"}  # 秘密を置くのが正しい場所（ただし git 除外が必要）

# 主要プロバイダーのキー形式
KEY_PATTERNS = {
    "OpenAI": re.compile(r"\bsk-(?!ant-)(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{20,}"),
    "Anthropic": re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"),
    "Google": re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    "Hugging Face": re.compile(r"\bhf_[A-Za-z0-9]{30,}"),
    "Groq": re.compile(r"\bgsk_[A-Za-z0-9]{40,}"),
    "AWS": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}
PLACEHOLDER = re.compile(r"(?i)your|example|xxxx|dummy|placeholder|changeme|<|\.\.\.")
LITERAL_SECRET = re.compile(r"""(?i)\b([A-Z_]*(api[_-]?key|secret|token|password))\s*[:=]\s*["']([^"'\s]{12,})["']""")

LLM_SDKS = {
    "openai": "OpenAI", "anthropic": "Anthropic", "google.genai": "Gemini (google-genai)",
    "google.generativeai": "Gemini (旧SDK)", "langchain": "LangChain", "litellm": "LiteLLM",
    "mistralai": "Mistral", "cohere": "Cohere", "groq": "Groq", "ollama": "Ollama", "boto3": "AWS (Bedrock?)",
    "llama_index": "LlamaIndex", "transformers": "Hugging Face Transformers",
}

# (正規表現, 重要度の目安, OWASP LLM カテゴリ, 説明)
CODE_PATTERNS = [
    (r"unsafe_allow_html\s*=\s*True", "中", "LLM05", "unsafe_allow_html=True: 入力やモデル出力を HTML として描画している可能性"),
    (r"components\.(v1\.)?html\(|\bst\.html\(", "中", "LLM05", "HTML の直接埋め込み（st.html / components.html）: 何を描画しているか確認"),
    (r"\beval\(|\bexec\(", "高", "LLM05/06", "eval/exec: 文字列をコードとして実行（モデル出力が入るなら重大）"),
    (r"subprocess\.|os\.system\(|os\.popen\(", "中", "LLM06", "外部コマンド実行: 引数にモデル出力や入力が入らないか確認"),
    (r"shell\s*=\s*True", "中", "LLM06", "shell=True: コマンドインジェクションの余地"),
    (r"pickle\.loads?\(|joblib\.load\(", "中", "LLM03", "pickle/joblib の読み込み: 改ざんファイルでコード実行されうる"),
    (r"torch\.load\((?![^)]*weights_only\s*=\s*True)", "中", "LLM03", "torch.load（weights_only=True なし）"),
    (r"trust_remote_code\s*=\s*True", "中", "LLM03", "trust_remote_code=True: 外部モデルのコードを実行"),
    (r"yaml\.load\((?![^)]*SafeLoader)", "中", "LLM03", "yaml.load（SafeLoader なし）"),
    (r"st\.(write|json)\(\s*st\.(secrets|session_state)\s*\)", "高", "LLM02", "st.secrets / st.session_state を丸ごと画面に表示"),
    (r"st\.(write|json|text|code)\(\s*(os\.environ|st\.secrets)", "高", "LLM02", "環境変数・secrets を画面に表示"),
    (r"\.execute\(\s*f[\"']|\.execute\([^)]*%\s*\(|\.execute\([^)]*\.format\(", "高", "LLM05", "SQL を文字列組み立てで実行（SQLインジェクション）"),
    (r"open\([^)]*(response|output|completion|answer|content)", "低", "LLM05", "モデル出力をファイルパスに使っている疑い"),
]
# 共有状態・エージェント機能など「読んで判断が必要」なものの目印
REVIEW_MARKERS = [
    (r"@st\.cache_resource|@st\.cache_data", "LLM02", "キャッシュ: ユーザー固有のデータ（会話・入力）を入れていると全ユーザーで共有される"),
    (r"^(messages|history|chat_history|conversations?|logs?)\s*(:\s*\w+)?\s*=\s*(\[|\{)", "LLM02", "モジュール直下の可変リスト/辞書: Streamlit では全セッションで共有される"),
    (r"\btools\s*=|function_call|tool_choice|bind_tools|create_.*agent|AgentExecutor", "LLM06", "ツール使用/エージェント: 各ツールの権限（実行・書き込み・外部通信）を確認"),
    (r"requests\.(get|post)\(|httpx\.(get|post)\(|urllib\.request\.urlopen\(", "LLM06", "外部 HTTP アクセス: URL がモデル出力や入力由来なら SSRF の余地"),
    (r"st\.file_uploader\(", "LLM01", "ファイルアップロード: 中身は外部の信頼できない入力（間接プロンプトインジェクション）"),
    (r"st\.query_params|st\.experimental_get_query_params", "LLM01", "URL パラメータを入力に使用"),
    (r"st\.login\(|streamlit_authenticator|st\.experimental_user|st\.user\b", "-", "認証の仕組みあり"),
    (r"max_tokens|max_output_tokens|max_completion_tokens", "LLM10", "出力トークン上限の指定あり"),
    (r"(?i)system(_instruction|_prompt)?\s*=", "LLM07", "システムプロンプト: 秘密情報（社内情報・キー・割引コード等）を入れていないか確認"),
]
KEY_VAR = r"\b\w*(api_?key|API_?KEY|secret|SECRET|token|TOKEN)\w*\b"
KEY_EXPOSURE = re.compile(
    r"(print|logging\.\w+|logger\.\w+|st\.(write|text|caption|markdown|code|info|error|warning|success|json|sidebar\.\w+))"
    r"\s*\(.*" + KEY_VAR
)
DEPLOY_SIGNALS = {
    "Dockerfile": "Docker", "docker-compose.yml": "Docker Compose", "compose.yaml": "Docker Compose",
    "Procfile": "Heroku 等", "app.yaml": "Google App Engine", "fly.toml": "Fly.io", "render.yaml": "Render",
    "railway.json": "Railway", "vercel.json": "Vercel", ".github/workflows": "GitHub Actions",
    "packages.txt": "Streamlit Community Cloud の可能性", ".devcontainer": "Codespaces / devcontainer",
}


def mask(s: str) -> str:
    return s[:4] + "*" * 8


def is_skipped(root: Path, p: Path) -> bool:
    parts = p.relative_to(root).parts
    return any(part in SKIP_DIRS or part.endswith("-workspace") for part in parts)


def iter_files(root: Path):
    for p in root.rglob("*"):
        if is_skipped(root, p) or not p.is_file():
            continue
        if (p.suffix in TEXT_SUFFIXES or p.name.startswith(".env")) and p.stat().st_size < 3_000_000:
            yield p


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def gitignore_covers(patterns: list[str], rel: str) -> bool:
    name = rel.split("/")[-1]
    for pat in patterns:
        p = pat.strip().rstrip("/")
        if not p or p.startswith("#") or p.startswith("!"):
            continue
        p = p.lstrip("/")
        rx = "^" + re.escape(p).replace(r"\*\*", ".*").replace(r"\*", "[^/]*") + "$"
        if re.match(rx, rel) or re.match(rx, name) or rel.startswith(p + "/"):
            return True
    return False


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    findings: list[tuple[str, str, str, str]] = []  # (重要度, OWASP, 場所, 内容)
    review: list[tuple[str, str, str]] = []
    ok: list[str] = []
    info: list[str] = []

    def add(sev, cat, where, msg):
        findings.append((sev, cat, where, msg))

    gi_lines = read(root / ".gitignore").splitlines()
    py_files = [p for p in root.rglob("*.py") if not is_skipped(root, p)]
    py_text = {p: read(p) for p in py_files}
    all_py = "\n".join(py_text.values())

    # 0. 概要: Streamlit / LLM SDK / デプロイの手がかり
    sdks = sorted({label for mod, label in LLM_SDKS.items()
                   if re.search(rf"^\s*(import|from)\s+{re.escape(mod)}\b", all_py, re.M)})
    info.append(f"Python ファイル: {len(py_files)} 個 / Streamlit 使用: {'あり' if 'streamlit' in all_py else 'なし'}")
    info.append(f"検出した LLM SDK: {', '.join(sdks) if sdks else 'なし'}")
    deploy = [f"{k}（{v}）" for k, v in DEPLOY_SIGNALS.items() if (root / k).exists()]
    readme = " ".join(read(p) for p in root.glob("README*"))
    if re.search(r"(?i)streamlit\.app|community cloud|公開して|公開中|hugging ?face spaces|https?://(?!localhost)", readme):
        deploy.append("README に公開URL/公開の記述")
    info.append(f"デプロイの手がかり: {', '.join(deploy) if deploy else 'なし（ローカル実行のみの可能性）'}")
    info.append(f"git リポジトリ: {'あり' if (root / '.git').exists() else 'なし'}")

    # 1. 秘密情報の混入
    hits = 0
    secret_files_found = []
    for p in iter_files(root):
        rel = p.relative_to(root).as_posix()
        in_secret_file = p.name in SECRET_FILES or p.name.startswith(".env.") and p.name != ".env.example"
        text = read(p)
        file_hits = 0
        for n, line in enumerate(text.splitlines(), 1):
            for provider, rx in KEY_PATTERNS.items():
                for m in rx.finditer(line):
                    if PLACEHOLDER.search(m.group()):
                        continue
                    file_hits += 1
                    if in_secret_file:
                        continue
                    hits += 1
                    sev = "高" if p.suffix in (".py", ".ipynb", ".toml", ".yaml", ".yml", ".md", ".sh") or rel.endswith(".example") else "中"
                    add(sev, "LLM02", f"{rel}:{n}", f"{provider} のキー形式の文字列 {mask(m.group())} が秘密ファイル以外にある")
            if p.suffix == ".py":
                for m in LITERAL_SECRET.finditer(line):
                    if PLACEHOLDER.search(m.group(3)) or any(rx.search(m.group(3)) for rx in KEY_PATTERNS.values()):
                        continue
                    hits += 1
                    add("高", "LLM02", f"{rel}:{n}", f"{m.group(1)} に文字列リテラル {mask(m.group(3))} を直書きしている疑い")
        if in_secret_file:
            secret_files_found.append((rel, file_hits))
    if hits == 0:
        ok.append("秘密ファイル（.env / secrets.toml）以外に既知形式の APIキーは見つからない")

    # 2. 秘密ファイルの git 除外
    for rel, n in secret_files_found:
        covered = gitignore_covers(gi_lines, rel)
        state = f"キー形式の値 {n} 個" if n else "既知形式のキーなし"
        if covered:
            ok.append(f"{rel} は .gitignore で除外されている（{state}）")
        else:
            add("高", "LLM02", ".gitignore", f"{rel}（{state}）が .gitignore で除外されていない。git に載ると公開される")
    if not any(gitignore_covers(gi_lines, x) for x in (".env",)) and not (root / ".env").exists():
        info.append(".env はない（今後作るなら .gitignore への追加が必要）")

    # 3. コードの危険パターン・キー露出
    for p, text in py_text.items():
        rel = p.relative_to(root).as_posix()
        if rel.startswith("tests/") or "/tests/" in rel:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if line.strip().startswith("#"):
                continue
            for pat, sev, cat, msg in CODE_PATTERNS:
                if re.search(pat, line):
                    add(sev, cat, f"{rel}:{n}", msg)
            if KEY_EXPOSURE.search(line) and "type=\"password\"" not in line:
                add("高", "LLM02", f"{rel}:{n}", "APIキー/秘密らしき変数を画面・ログに出力している疑い")
            for pat, cat, msg in REVIEW_MARKERS:
                if re.search(pat, line):
                    review.append((cat, f"{rel}:{n}", msg))

    # 4. Streamlit 設定
    cfg = root / ".streamlit" / "config.toml"
    text = read(cfg) if cfg.exists() else ""
    m = re.search(r'^\s*address\s*=\s*"([^"]*)"', text, re.M)
    if m and m.group(1) in ("localhost", "127.0.0.1"):
        ok.append(f"server.address = {m.group(1)}（このPCからのみ接続可）")
    elif m:
        add("中", "-", ".streamlit/config.toml", f'server.address = "{m.group(1)}": 同じネットワークの他人が接続できる')
    else:
        add("中※", "-", ".streamlit/config.toml",
            "server.address 未設定: Streamlit は既定で全インターフェースで待ち受ける（ローカル利用なら同じWi-Fiの他人が接続できる。"
            "クラウド/コンテナで公開する前提なら問題なし）")
    for key in ("enableXsrfProtection", "enableCORS"):
        if re.search(rf"^\s*{key}\s*=\s*false", text, re.M):
            add("中", "-", ".streamlit/config.toml", f"{key} = false: ブラウザ経由の攻撃対策が無効")
    sed = re.search(r'^\s*showErrorDetails\s*=\s*"?(\w+)"?', text, re.M)
    if not sed or sed.group(1).lower() in ("true", "full", "stacktrace"):
        info.append("client.showErrorDetails が既定/詳細表示: 公開時は例外のスタックトレースが利用者に見える")
    mus = re.search(r"^\s*maxUploadSize\s*=\s*(\d+)", text, re.M)
    if "file_uploader" in all_py:
        info.append(f"server.maxUploadSize = {mus.group(1) + 'MB' if mus else '既定（200MB）'}")

    # 5. 平文で保存されるデータ
    data_files = [p.relative_to(root).as_posix() for p in iter_files(root)
                  if p.suffix in (".json", ".jsonl", ".csv", ".log", ".db", ".sqlite")
                  and p.name not in ("package.json", "tsconfig.json") and not p.name.startswith(".")]
    data_files += [p.relative_to(root).as_posix() for p in root.rglob("*.db") if not is_skipped(root, p)]
    data_files += [p.relative_to(root).as_posix() for p in root.rglob("*.sqlite*") if not is_skipped(root, p)]
    for rel in sorted(set(data_files)):
        tag = "git除外済み" if gitignore_covers(gi_lines, rel) else "git除外なし"
        info.append(f"データファイル {rel}（{tag}）: 会話・入力が平文で残っていないか確認")

    if "onedrive" in str(root).lower() or "dropbox" in str(root).lower():
        add("低", "LLM02", str(root), "クラウド同期フォルダ内: 秘密ファイルやデータファイルもアップロードされる")

    # 6. 依存関係
    req = root / "requirements.txt"
    if req.exists():
        loose = [ln.strip() for ln in read(req).splitlines()
                 if ln.strip() and "==" not in ln and not ln.startswith(("#", "-"))]
        if loose:
            add("低", "LLM03", "requirements.txt", f"バージョン固定なし（{', '.join(loose)}）")
        if shutil.which("pip-audit"):
            try:
                r = subprocess.run(["pip-audit", "-r", str(req), "--progress-spinner", "off"], capture_output=True,
                                   text=True, timeout=180, encoding="utf-8", errors="replace")
                if r.returncode == 0:
                    ok.append("pip-audit: 既知の脆弱性なし")
                else:
                    add("要確認", "LLM03", "requirements.txt", "pip-audit の結果:\n" + (r.stdout + r.stderr).strip()[-2000:])
            except (subprocess.SubprocessError, OSError) as e:
                info.append(f"pip-audit の実行に失敗: {e}")
        else:
            info.append("pip-audit 未インストール: 依存ライブラリの既知脆弱性は未確認（pip install pip-audit）")
    elif (root / "pyproject.toml").exists():
        info.append("requirements.txt なし（pyproject.toml の依存を手動で確認）")

    order = {"高": 0, "中": 1, "中※": 2, "要確認": 3, "低": 4}
    findings.sort(key=lambda f: order.get(f[0], 9))
    print(f"# 機械スキャン結果: {root}\n")
    print("## 概要")
    for i in info[:4]:
        print(f"- {i}")
    print("\n## 指摘候補（※ 重要度は暫定。利用形態に合わせて調整し、誤検知は除くこと）")
    for sev, cat, where, msg in findings:
        print(f"- [{sev}] [{cat}] {where} — {msg}")
    print("\n## 読んで判断が必要な箇所")
    for cat, where, msg in review:
        print(f"- [{cat}] {where} — {msg}")
    print("\n## 問題なし")
    for o in ok:
        print(f"- {o}")
    print("\n## 参考情報")
    for i in info[4:]:
        print(f"- {i}")
    print("\n（機械的なチェックのみ。コードを読んでの確認は別途行うこと）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
