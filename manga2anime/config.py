from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


_DOTENV_LOADED = False


@dataclass(frozen=True)
class AppConfig:
    openai_api_key: str | None
    vision_model: str
    image_model: str
    output_dir: str
    fps: int
    max_pages: int
    max_shots: int
    tts_model: str
    tts_voice: str

    @property
    def has_openai_key(self) -> bool:
        return bool(self.openai_api_key)

    @classmethod
    def from_env(cls) -> "AppConfig":
        _load_dotenv_once()
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            vision_model=os.getenv("OPENAI_VISION_MODEL", "gpt-4o"),
            image_model=os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"),
            output_dir=os.getenv("MANGA2ANIME_OUTPUT_DIR", "outputs"),
            fps=int(os.getenv("MANGA2ANIME_FPS", "24")),
            max_pages=int(os.getenv("MANGA2ANIME_MAX_PAGES", "20")),
            max_shots=int(os.getenv("MANGA2ANIME_MAX_SHOTS", "8")),
            tts_model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
            tts_voice=os.getenv("OPENAI_TTS_VOICE", "alloy"),
        )


def _load_dotenv_once() -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True

    env_path = Path(".env")
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
