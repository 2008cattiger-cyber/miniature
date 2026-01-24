import json
from pathlib import Path


DATA_PATH = Path("data/masterclasses.json")


def load_masterclasses():
    """
    Возвращает список мастер-классов вида:
    [{"title": "...", "url": "..."}]
    """
    if not DATA_PATH.is_file():
        return []

    try:
        with DATA_PATH.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return []

    if not isinstance(raw, list):
        return []

    items = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title", "")).strip()
        url = str(entry.get("url", "")).strip()
        if title and url:
            items.append({"title": title, "url": url})

    return items
