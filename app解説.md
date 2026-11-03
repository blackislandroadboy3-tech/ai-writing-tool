# 🔰 AIライティングツール `app.py` を読んでみよう：Streamlitアプリの動き方

## はじめに

前回作ったAIライティングツールは、ブラウザで文章を入れてボタンを押すと、AIが記事やメールを書いてくれるアプリでした。この記事では、その画面を作っている `app.py` を上から順に読んでいきます。

先に結論を言うと、`app.py` は次の6つのブロックでできています。

```
① 準備（ライブラリの読み込み・設定）
② サイドバー（機能の選択・品質・APIキー・履歴）
③ 履歴の表示（履歴を開いているときだけ）
④ 入力フォーム（機能ごとに入力欄を出し分ける）
⑤ 生成（AIに依頼して、結果を少しずつ表示）
⑥ 結果の表示（プレビュー・コピー・保存）
```

## まず知っておきたいこと：Streamlitは「毎回まるごと実行し直す」

コードを読む前に、これだけは押さえてください。

> **Streamlitは、ボタンを押すなど画面を操作するたびに、`app.py` を1行目から最後までもう一度実行します。**

普通のプログラムは「ボタンが押されたらこの関数を呼ぶ」という書き方をします。Streamlitは違って、毎回すべてを描き直しながら、いまの入力値を見て表示を決めます。

ただ、毎回やり直すと変数の中身は消えてしまいます。そこで、消したくない値は **`st.session_state`**（画面を操作しても消えない保存箱）に入れておきます。このアプリでも「いま開いている履歴」と「生成した結果」をここに入れています。

この「毎回やり直す」と「保存箱」の2つが分かれば、あとはスムーズに読めます。

## ① 準備

```python
import history
import prompts
from writer import QUALITY, RefusalError, stream_text

load_dotenv(override=True)

st.set_page_config(page_title="AIライティングツール", page_icon="✍️", layout="wide")
```

- `history`、`prompts`、`writer` は、自分で作ったほかのファイルです。役割は分担されています。
  - `prompts.py`：AIへの指示文（プロンプト）を作る
  - `writer.py`：Gemini APIを呼び出す
  - `history.py`：履歴を保存する
  - `app.py`：画面を担当し、これらを組み合わせる
- `load_dotenv(override=True)` は、`.env` ファイルのAPIキーを読み込みます。`override=True` があるので、`.env` を書き換えるとブラウザを再読み込みするだけで新しい値が使われます。
- `set_page_config` は、ブラウザのタブに出るタイトルとアイコン、横幅を広く使う設定です。

## ② サイドバー

```python
with st.sidebar:
    st.title("✍️ AIライティング")
    tool = st.radio("機能", list(prompts.TOOLS.keys()), label_visibility="collapsed")
    quality = st.select_slider("品質", options=list(QUALITY.keys()), value="標準")
```

`with st.sidebar:` の中に書いたものは、画面左のサイドバーに表示されます。

- **機能の選択**：`prompts.TOOLS` の名前（「📝 ブログ記事」など）をラジオボタンで並べています。選ばれた名前が `tool` に入り、この値で以降の表示が切り替わります。
- **品質**：「速さ優先 / 標準 / 高品質」を選ぶスライダーです。実際に使うAIモデルは `writer.py` の `QUALITY` で決まっています。

```python
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        api_key = st.text_input("Gemini APIキー", type="password", ...)
```

`.env` にAPIキーがあればそれを使います。無ければ入力欄を出します。`type="password"` なので、入力した文字は「●●●」で隠れます。

```python
    with st.expander("🕘 履歴"):
        items = history.load()
        for idx, item in enumerate(items[:30]):
            if st.button(f"{item['time']} {item['tool']}", key=f"h{idx}", ...):
                st.session_state.viewing = item
```

履歴は折りたたみ（`expander`）の中にあり、新しい順に最大30件のボタンが並びます。
`st.button` は、押された回の実行でだけ `True` になります。そのときに、選んだ履歴を保存箱 `st.session_state.viewing` に入れています。

## ③ 履歴の表示

```python
if "viewing" in st.session_state:
    item = st.session_state.viewing
    st.subheader(f"履歴: {item['tool']}（{item['time']}）")
    if st.button("← 戻る"):
        del st.session_state.viewing
        st.rerun()
    st.markdown(item["output"])
    st.code(item["output"], language=None, wrap_lines=True)
    st.stop()
```

保存箱に `viewing` が入っていれば、その履歴を表示します。

- `st.markdown` は見出しや箇条書きを整えて表示します。`st.code` は元のテキストをそのまま表示し、右上のボタンでコピーできます。
- **最後の `st.stop()`** で、実行をここで止めます。これより下の入力フォームは表示されず、画面には履歴だけが出ます。
- 「← 戻る」を押すと、`viewing` を消してから `st.rerun()`（すぐに最初から実行し直す）を呼びます。次の実行では `viewing` が無いので、いつもの入力画面に戻ります。

## ④ 入力フォーム

```python
st.header(tool)

inputs: dict = {}
with st.form(key=f"form_{tool}"):
    if tool == "📝 ブログ記事":
        inputs["theme"] = st.text_input("テーマ *", placeholder="例: 初心者向け 家庭菜園の始め方")
        ...
        required = ["theme"]
    elif tool == "✉️ メール返信":
        ...
    else:  # 自由リクエスト
        inputs["request"] = st.text_area("依頼内容 *", ...)
        required = ["request"]

    submitted = st.form_submit_button("✨ 生成する", type="primary", ...)
```

ここが一番長い部分ですが、やっていることは単純です。

1. **`if tool == ...` で機能ごとに入力欄を出し分けます。** ブログならテーマ・読者・文字数、メールなら受信メール・相手との関係、という具合です。
2. **入力された値は `inputs` という辞書にまとめます。** 例：`inputs["theme"] = "家庭菜園"`
3. **`required` には必須項目の名前を入れます。** ラベルに `*` が付いている項目です。

ポイントは **`st.form`** です。フォームの外に入力欄を置くと、1文字打つたびにアプリ全体が実行し直されます。フォームの中なら、**「✨ 生成する」を押すまで実行し直されません。** 押された回だけ `submitted` が `True` になります。

```python
def tone(key):
    return st.selectbox("トーン", prompts.TONES, key=key)
```

「トーン」の選択欄は多くの機能で使うので、小さな関数にまとめています。`key` を機能ごとに変えている（`"blog_tone"`、`"mail_tone"` など）ので、機能ごとに別の値として扱われます。

💡 **`inputs` のキー名は `prompts.py` 側と同じでなければいけません。** たとえば `prompts.py` のブログ用の関数は `i['theme']` を読むので、こちらでも `inputs["theme"]` という名前で入れています。

## ⑤ 生成

### 5-1. 送信前のチェック

```python
if submitted:
    if not api_key:
        st.error("APIキーを設定してください（サイドバー または .env）")
        st.stop()
    if any(not str(inputs[k]).strip() for k in required):
        st.warning("* の項目を入力してください")
        st.stop()
```

ボタンが押されたら、まず確認をします。

- APIキーが無ければ、エラーを出して止めます。
- 必須項目（`required`）のどれかが空なら、警告を出して止めます。`.strip()` で前後の空白を取り除くので、スペースだけの入力も「空」とみなされます。

### 5-2. AIに依頼する

```python
    system, user = prompts.TOOLS[tool](inputs)
    client = genai.Client(api_key=api_key)
    try:
        with st.spinner("考え中…"):
            output = st.write_stream(stream_text(client, system, user, QUALITY[quality]))
```

1. `prompts.TOOLS[tool]` で、選んだ機能のプロンプト作成関数を取り出し、`inputs` を渡します。返ってくるのは2つの文章です。
   - `system`：AIの役割（例：「あなたは日本語のプロのライターです」）
   - `user`：具体的な依頼文
2. `genai.Client` で、Gemini APIにつなぐ準備をします。
3. **`st.write_stream`** に `stream_text(...)` を渡すと、AIが書いた文章が届いた分から画面に表示されます。ChatGPTのように文字が流れて出てくるのはこの仕組みです。全部表示し終わると、完成した文章が `output` に入ります。
4. `st.spinner` は、待っている間に「考え中…」とくるくる回る表示を出します。

### 5-3. エラーへの対応

```python
    except RefusalError as e:
        st.error(str(e))
    except errors.ClientError as e:
        if e.code in (400, 401, 403) and "API key" in str(e):
            st.error("APIキーが正しくありません")
        elif e.code == 429:
            st.error("無料枠の上限、またはリクエストが多すぎます。...")
        elif e.code == 404:
            st.error(f"モデル「{QUALITY[quality]}」が見つかりません。...")
        ...
    except errors.ServerError as e:
        st.error(f"Gemini側でエラーが発生しました（{e.code}）。...")
```

APIの呼び出しは失敗することがあります。このアプリは、失敗の種類ごとにわかりやすい日本語のメッセージを出します。

| 種類 | 意味 |
|---|---|
| `RefusalError` | 安全フィルターでAIが生成を断った（`writer.py` で定義した独自のエラー） |
| 400 / 401 / 403 | APIキーが間違っている |
| 429 | 使いすぎ（無料枠の上限など） |
| 404 | 指定したモデルが存在しない |
| `ServerError`（5xx） | Gemini側の問題。前回の動作確認で出た503（混雑中）もここに入ります |

### 5-4. 保存して描き直す

```python
    st.session_state[result_key] = output   # result_key = f"result_{tool}"
    history.add(tool, inputs, output)
    st.rerun()
```

成功したら、次の3つを行います。

1. 結果を保存箱に入れます。キーが `result_ブログ記事` のように機能ごとに分かれているので、ほかの機能に切り替えて戻っても、それぞれの結果が残っています。
2. `history.json` に履歴として保存します。
3. `st.rerun()` で最初から実行し直します。サイドバーの履歴は②で先に読み込まれているので、描き直さないと新しい履歴が一覧に出ません。描き直すと、結果は次の⑥でタブ付きの表示に切り替わります。

## ⑥ 結果の表示

```python
if result_key in st.session_state:
    output = st.session_state[result_key]
    tab_view, tab_copy = st.tabs(["プレビュー", "コピー用テキスト"])
    with tab_view:
        st.markdown(output)
    with tab_copy:
        st.code(output, language=None, wrap_lines=True)
    st.download_button("⬇️ Markdownで保存", output, file_name="output.md", mime="text/markdown")
```

保存箱に結果があれば表示します。

- **プレビュー**タブ：見出しや太字を整えた読みやすい表示
- **コピー用テキスト**タブ：元のテキストのまま表示し、ワンクリックでコピーできる
- **⬇️ Markdownで保存**：`output.md` というファイルとしてダウンロードできる

## 全体の流れをおさらい

「ブログ記事を作る」ときの流れを追うと、こうなります。

```
[画面を開く]
  → ①準備 → ②サイドバー → ④入力フォーム（ブログ用の欄を表示）
  → submitted は False なので⑤は飛ばす → ⑥まだ結果は無い

[テーマを入れて「✨ 生成する」を押す]
  → 最初から実行し直し → ④で submitted が True に
  → ⑤チェック → プロンプト作成 → AIの文章を少しずつ表示
  → 結果を保存箱と履歴に保存 → st.rerun()

[最初から実行し直し]
  → ②履歴に新しい1件が増える → ⑥保存箱の結果をタブで表示 ✨
```

## まとめ

- Streamlitは**操作のたびに `app.py` を最初から実行し直す**。消したくない値は `st.session_state` に入れる。
- `st.form` を使うと、**ボタンを押すまで実行し直されない**。
- `st.stop()` は「ここで終わり」、`st.rerun()` は「すぐに最初からやり直し」。
- `app.py` は画面を担当し、プロンプト作りは `prompts.py`、API呼び出しは `writer.py`、履歴の保存は `history.py` に任せている。

次に読むなら、AIへの指示文がどう組み立てられているかがわかる `prompts.py` がおすすめです。
