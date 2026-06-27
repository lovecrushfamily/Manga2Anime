from __future__ import annotations

import base64
from pathlib import Path


def image_to_data_url(path: Path) -> str:
    mime = "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def extract_output_text(response) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return text
    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        content = _value(item, "content") or []
        for part in content:
            value = _value(part, "text")
            if value:
                chunks.append(value)
    return "\n".join(chunks)


def extract_image_b64(response) -> str | None:
    for item in getattr(response, "output", []) or []:
        item_type = _value(item, "type")
        if item_type == "image_generation_call":
            return _value(item, "result")
    return None


def _value(item, key: str):
    value = getattr(item, key, None)
    if value is not None:
        return value
    if isinstance(item, dict):
        return item.get(key)
    return None
