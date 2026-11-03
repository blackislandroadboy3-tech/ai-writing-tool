"""生成履歴をローカルの JSON ファイルに保存する。"""

import json
from datetime import datetime
from pathlib import Path

HISTORY_FILE = Path(__file__).parent / "history.json"
MAX_ITEMS = 200


def load() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def add(tool: str, inputs: dict, output: str) -> None:
    items = load()
    items.insert(0, {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "tool": tool,
        "inputs": inputs,
        "output": output,
    })
    HISTORY_FILE.write_text(
        json.dumps(items[:MAX_ITEMS], ensure_ascii=False, indent=2), encoding="utf-8"
    )


def clear() -> None:
    HISTORY_FILE.unlink(missing_ok=True)
