# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A personal Japanese-language AI writing tool: a single-page Streamlit app that calls the Gemini API (`google-genai` SDK) with streaming. UI text, prompts, and code comments are in Japanese — keep new user-facing strings in Japanese.

## Commands

```
pip install -r requirements.txt
copy .env.example .env      # then set GEMINI_API_KEY
streamlit run app.py
```

Development (tests and lint never call the Gemini API):

```
pip install -r requirements-dev.txt
python -m pytest                                   # all tests
python -m pytest tests/test_prompts.py -k sns      # a single test
python -m ruff check .                             # lint (config in pyproject.toml; E501 off for long Japanese prompt lines)
```

`tests/test_history.py` patches `history.HISTORY_FILE` to a temp path, and `tests/test_writer.py` uses a fake client built from `SimpleNamespace` chunks. Follow the same patterns so tests never touch the real `history.json` or the network. `.env` is loaded with `override=True`, so edits to it take effect on a browser reload. If no key is in `.env`, the sidebar asks for one.

## Architecture

- **`prompts.py`**: the registry of writing features. `TOOLS` maps a display label (emoji + Japanese name) to a builder function `build(inputs: dict) -> (system, user)`. Option tables (`TONES`, `SUMMARY_STYLES`, `REWRITE_MODES`, `SNS_PLATFORMS`, `COPY_KINDS`) are dicts/lists whose keys appear in the UI and whose values are injected into the prompt. Most tools share `BASE_SYSTEM`, which tells the model to output only the requested text, formatted as Markdown.
- **`app.py`**: the Streamlit UI. The sidebar radio selects a `TOOLS` key. The form is a long `if tool == "<label>":` chain that fills `inputs` and a `required` list. On submit, it calls `prompts.TOOLS[tool](inputs)`, streams the result through `st.write_stream`, maps `google.genai.errors` codes (400/401/403/404/429/5xx) to Japanese messages, saves the output in `st.session_state[f"result_{tool}"]`, writes it to history, and calls `st.rerun()`.
- **`writer.py`**: `QUALITY` maps the quality slider (速さ優先 / 標準 / 高品質) to Gemini model IDs. Change models here; a 404 in the app points users to this dict. `stream_text` is a generator: it raises `RefusalError` when a prompt is blocked or the finish reason is a safety reason, and adds a note when it stops at `MAX_TOKENS`.
- **`history.py`**: saves generations to `history.json` next to the code (newest first, at most 200 items, ignored by git). The sidebar shows the first 30, and clicking one sets `st.session_state.viewing`.

### Adding a new writing feature

The tool label string must match exactly in three places:
1. Write a builder function in `prompts.py` and register it in `TOOLS`.
2. Add a matching `elif tool == "<same label>":` branch in `app.py`'s form. It fills `inputs` with exactly the keys the builder reads and sets `required`.
3. Add sample inputs for the new label to `SAMPLE_INPUTS` in `tests/test_prompts.py`. `test_app_form_has_branch_for_every_tool` fails if the labels in `prompts.py` and `app.py` drift apart. 💬 自由リクエスト is the exception, because it is handled by `else`.
4. Update the feature list in `README.md`.
