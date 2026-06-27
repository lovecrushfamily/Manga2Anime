from __future__ import annotations

import json
import math
from typing import Any

from openai import OpenAI

from manga2anime.config import AppConfig
from manga2anime.models import DirectorPlan, PageImage, Shot
from manga2anime.openai_utils import extract_output_text, image_to_data_url
from manga2anime.style import build_style_directive


CAMERA_MOTIONS = ["slow_push", "pan_left", "pan_right", "zoom_in", "tilt_up", "impact_shake"]


def build_director_plan(
    pages: list[PageImage],
    style_prompt: str,
    config: AppConfig,
    max_shots: int,
    target_duration: int,
    direction_context: str = "",
) -> DirectorPlan:
    if config.has_openai_key:
        try:
            return _build_openai_plan(
                pages,
                style_prompt,
                config,
                max_shots,
                target_duration,
                direction_context,
            )
        except Exception as exc:  # noqa: BLE001 - the API should still produce a demo render.
            return _fallback_plan(
                pages,
                style_prompt,
                max_shots,
                target_duration,
                note=str(exc),
                direction_context=direction_context,
            )
    return _fallback_plan(
        pages,
        style_prompt,
        max_shots,
        target_duration,
        note="No OPENAI_API_KEY set.",
        direction_context=direction_context,
    )


def _build_openai_plan(
    pages: list[PageImage],
    style_prompt: str,
    config: AppConfig,
    max_shots: int,
    target_duration: int,
    direction_context: str,
) -> DirectorPlan:
    client = OpenAI(api_key=config.openai_api_key)
    sample_pages = _sample_pages(pages, max_count=min(6, len(pages)))
    style_directive = build_style_directive(style_prompt)

    content: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": (
                "You are an anime director adapting a manga chapter into a 15-30 second "
                "black-and-white fanmade highlight. Analyze the uploaded manga pages: panels, "
                "characters, action beats, emotional beats, and pacing. Return only JSON with "
                "this shape: {\"chapter_summary\": string, \"style_directive\": string, "
                "\"studio_roles\": {\"director\": string, \"cameraman\": string, "
                "\"animation_director\": string, \"subtitle_adapter\": string, "
                "\"voice_director\": string}, "
                "\"shots\": [{\"source_page\": number, \"beat\": string, "
                "\"camera_motion\": \"slow_push|pan_left|pan_right|zoom_in|tilt_up|impact_shake\", "
                "\"transition\": string, \"duration\": number, \"frame_prompt\": string, "
                "\"animation_notes\": string, \"subtitle_ja\": string, \"voice_line_ja\": string}]}. "
                f"Create {max_shots} or fewer shots with total duration near {target_duration} seconds. "
                "The source frames are cleaned plates with dialogue removed; never put speech bubbles, "
                "captions, subtitles, sound effects, or readable text inside generated frames. "
                "Character continuity is mandatory: frame_prompt must preserve the exact face, "
                "hairstyle, costume, proportions, line weight, and manga style from the referenced "
                "source page. Do not ask for a redesigned, generic, beautified, or different-looking "
                "character. Camera angle may change only when identity remains unmistakable. "
                "The final video may have Japanese voiceover/subtitle metadata outside the manga art. "
                "Keep Japanese lines short and suitable for anime dubbing. "
                f"Extra direction context: {direction_context}\n"
                f"{style_directive}"
            ),
        }
    ]
    for page in sample_pages:
        content.append({"type": "input_image", "image_url": image_to_data_url(page.path)})

    response = client.responses.create(
        model=config.vision_model,
        input=[{"role": "user", "content": content}],
    )
    payload = _parse_json(extract_output_text(response))
    return _plan_from_payload(payload, pages, style_directive, max_shots, target_duration)


def _plan_from_payload(
    payload: dict[str, Any],
    pages: list[PageImage],
    style_directive: str,
    max_shots: int,
    target_duration: int,
) -> DirectorPlan:
    shots: list[Shot] = []
    raw_shots = payload.get("shots") or []
    for index, raw in enumerate(raw_shots[:max_shots]):
        page = int(raw.get("source_page") or _page_for_index(index, len(pages), max_shots))
        page = min(max(page, 1), len(pages))
        motion = raw.get("camera_motion") if raw.get("camera_motion") in CAMERA_MOTIONS else "slow_push"
        shots.append(
            Shot(
                source_page=page,
                beat=str(raw.get("beat") or f"Highlight beat from page {page}"),
                camera_motion=motion,
                transition=str(raw.get("transition") or "cinematic cut"),
                duration=float(raw.get("duration") or target_duration / max(1, max_shots)),
                frame_prompt=str(raw.get("frame_prompt") or "black-and-white anime action frame"),
                animation_notes=str(raw.get("animation_notes") or ""),
                subtitle_ja=str(raw.get("subtitle_ja") or ""),
                voice_line_ja=str(raw.get("voice_line_ja") or ""),
            )
        )
    if not shots:
        return _fallback_plan(pages, style_directive, max_shots, target_duration)
    return DirectorPlan(
        chapter_summary=str(payload.get("chapter_summary") or "Manga chapter highlight."),
        style_directive=str(payload.get("style_directive") or style_directive),
        studio_roles=_studio_roles_from_payload(payload),
        shots=_normalize_durations(shots, target_duration),
    )


def _fallback_plan(
    pages: list[PageImage],
    style_prompt: str,
    max_shots: int,
    target_duration: int,
    note: str | None = None,
    direction_context: str = "",
) -> DirectorPlan:
    shot_count = min(max_shots, max(1, len(pages)))
    duration = target_duration / shot_count
    shots = []
    for index in range(shot_count):
        page = _page_for_index(index, len(pages), shot_count)
        shots.append(
            Shot(
                source_page=page,
                beat=f"Directed manga beat from page {page}",
                camera_motion=CAMERA_MOTIONS[index % len(CAMERA_MOTIONS)],
                transition="ink-smear cinematic cut",
                duration=duration,
                frame_prompt=(
                    f"Black-and-white anime line art action frame from cleaned manga page {page}. "
                    "No speech bubbles, no captions, no subtitles, no readable text. "
                    "Preserve the exact same character face, hairstyle, costume, proportions, "
                    "silhouette, and original manga line style from the source page; do not redesign "
                    "the character. "
                    f"Style direction: {style_prompt}. Direction context: {direction_context[:700]}"
                ),
                animation_notes="Animate as a finished anime cut: camera move, foreground energy, and clean transition.",
                subtitle_ja=f"第{index + 1}カット。物語が動き出す。",
                voice_line_ja=f"第{index + 1}カット。物語が動き出す。",
            )
        )
    suffix = f" Fallback reason: {note}" if note else ""
    return DirectorPlan(
        chapter_summary=(
            f"Auto-directed highlight based on {len(pages)} cleaned manga page(s), with dialogue "
            f"kept out of frames.{suffix}"
        ),
        style_directive=build_style_directive(style_prompt),
        studio_roles={
            "director": "Fallback director keeps the uploaded manga content as the story source.",
            "cameraman": "Chooses simple pan, zoom, tilt, and impact-shake moves from page order.",
            "animation_director": "Uses cleaned manga plates as short anime cuts.",
            "subtitle_adapter": "Creates short Japanese cue metadata outside the manga frame art.",
            "voice_director": "Creates short Japanese voiceover lines when TTS is enabled.",
        },
        shots=shots,
    )


def _sample_pages(pages: list[PageImage], max_count: int) -> list[PageImage]:
    if len(pages) <= max_count:
        return pages
    indexes = sorted({round(i * (len(pages) - 1) / (max_count - 1)) for i in range(max_count)})
    return [pages[index] for index in indexes]


def _page_for_index(index: int, page_count: int, shot_count: int) -> int:
    if shot_count <= 1:
        return 1
    return 1 + math.floor(index * max(page_count - 1, 0) / max(shot_count - 1, 1))


def _normalize_durations(shots: list[Shot], target_duration: int) -> list[Shot]:
    total = sum(max(0.5, shot.duration) for shot in shots)
    if total <= 0:
        return shots
    scale = target_duration / total
    return [
        Shot(
            source_page=shot.source_page,
            beat=shot.beat,
            camera_motion=shot.camera_motion,
            transition=shot.transition,
            duration=max(1.0, shot.duration * scale),
            frame_prompt=shot.frame_prompt,
            animation_notes=shot.animation_notes,
            subtitle_ja=shot.subtitle_ja,
            voice_line_ja=shot.voice_line_ja,
        )
        for shot in shots
    ]


def _studio_roles_from_payload(payload: dict[str, Any]) -> dict[str, str]:
    raw = payload.get("studio_roles")
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if str(value).strip()}


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)
