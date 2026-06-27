from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from openai import OpenAI

from manga2anime.config import AppConfig
from manga2anime.video import _ffmpeg_path


def generate_japanese_voiceover(
    script: str,
    config: AppConfig,
    output_path: Path,
) -> tuple[Path | None, str]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    script = script.strip()
    if not script:
        return None, "empty_script"
    if not config.has_openai_key:
        return None, "openai_not_configured"

    client = OpenAI(api_key=config.openai_api_key)
    speech_args: dict[str, Any] = {
        "model": config.tts_model,
        "voice": config.tts_voice,
        "input": script,
        "instructions": (
            "Speak in Japanese as an anime narrator/voice actor. Dramatic but clean, "
            "short lines, no sound effects, no English explanation."
        ),
        "response_format": "mp3",
    }
    try:
        response = client.audio.speech.create(**speech_args)
    except TypeError:
        speech_args.pop("instructions", None)
        response = client.audio.speech.create(**speech_args)
    except Exception as exc:  # noqa: BLE001 - keep video rendering usable if TTS is unavailable.
        return None, f"openai_tts_failed:{type(exc).__name__}"
    response.write_to_file(output_path)
    return output_path, "openai_tts"


def mux_audio(video_path: Path, audio_path: Path | None, output_path: Path) -> Path:
    if audio_path is None or not audio_path.exists():
        return video_path
    ffmpeg = _ffmpeg_path()
    duration = _video_duration_seconds(video_path, ffmpeg)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
    ]
    if duration:
        command.extend(["-t", f"{duration:.3f}"])
    command.extend(["-movflags", "+faststart", str(output_path)])
    subprocess.run(command, check=True)
    return output_path


def _video_duration_seconds(video_path: Path, ffmpeg: str) -> float | None:
    probe = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(video_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", probe.stderr + probe.stdout)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
