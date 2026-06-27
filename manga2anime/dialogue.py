from __future__ import annotations

import json
import re
from dataclasses import dataclass

from openai import OpenAI

from manga2anime.config import AppConfig
from manga2anime.models import PageImage
from manga2anime.openai_utils import extract_output_text, image_to_data_url


TIMECODE_RE = re.compile(r"^\d{1,2}:\d{2}:\d{2}[,.]\d{3}\s+-->\s+\d{1,2}:\d{2}:\d{2}[,.]\d{3}")


@dataclass(frozen=True)
class DialogueScript:
    text: str
    cue_count: int
    source: str


def build_dialogue_script(
    pages: list[PageImage],
    config: AppConfig,
    subtitle_text: str | None,
) -> DialogueScript:
    if subtitle_text and subtitle_text.strip():
        return parse_subtitle_text(subtitle_text, source="subtitle_upload")
    if config.has_openai_key:
        try:
            return extract_dialogue_with_vision(pages, config)
        except Exception as exc:  # noqa: BLE001 - dialogue extraction is helpful, not required.
            return DialogueScript(text=f"OCR dialogue extraction failed: {exc}", cue_count=0, source="ocr_failed")
    return DialogueScript(text="", cue_count=0, source="none")


def parse_subtitle_text(text: str, source: str) -> DialogueScript:
    lines = []
    for raw_line in text.replace("\ufeff", "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.isdigit() or TIMECODE_RE.match(line) or line.upper() == "WEBVTT":
            continue
        lines.append(line)
    return DialogueScript(text="\n".join(lines), cue_count=len(lines), source=source)


def extract_dialogue_with_vision(pages: list[PageImage], config: AppConfig) -> DialogueScript:
    client = OpenAI(api_key=config.openai_api_key)
    sampled = pages[: min(len(pages), 10)]
    content = [
        {
            "type": "input_text",
            "text": (
                "Extract visible character dialogue and narration from these manga pages. "
                "Return JSON only: {\"dialogue\": [\"line 1\", \"line 2\"]}. "
                "Do not describe sound effects unless they are important story text."
            ),
        }
    ]
    for page in sampled:
        content.append({"type": "input_image", "image_url": image_to_data_url(page.path)})
    response = client.responses.create(
        model=config.vision_model,
        input=[{"role": "user", "content": content}],
    )
    payload = _parse_json(extract_output_text(response))
    lines = [str(line).strip() for line in payload.get("dialogue", []) if str(line).strip()]
    return DialogueScript(text="\n".join(lines), cue_count=len(lines), source="openai_vision_ocr")


def decode_optional_text(data: bytes | None) -> str | None:
    if not data:
        return None
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)

