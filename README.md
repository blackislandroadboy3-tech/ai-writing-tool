# AIライティングツール

Gemini API を使った個人用ライティングツールです。

## 機能
- 📝 ブログ記事作成
- ✉️ メール返信文の作成
- 📄 要約（3行 / 箇条書き / 詳しめ / 一言）
- ✏️ 校正・リライト（校正 / 読みやすく / フォーマル / カジュアル / 短く / 詳しく）
- 📱 SNS投稿作成（X / Instagram / LinkedIn など）
- 🌐 翻訳
- 💡 タイトル・キャッチコピー案
- 💬 自由リクエスト
- 🕘 生成履歴（history.json に保存）、Markdownダウンロード

## セットアップ
```
pip install -r requirements.txt
copy .env.example .env   # .env に APIキーを記入
streamlit run app.py
```

APIキーは https://aistudio.google.com/apikey で無料で取得できます。
品質（速さ優先 / 標準 / 高品質）ごとのモデルは `writer.py` の `QUALITY` で変更できます。

## 開発用（テスト・Lint）
```
pip install -r requirements-dev.txt
python -m pytest
python -m ruff check .
```
テストは Gemini API を呼ばないので、APIキーなしで実行できます。
