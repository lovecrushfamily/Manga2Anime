from __future__ import annotations

import subprocess
import tempfile
import shutil
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

from manga2anime.models import DirectorPlan, RenderFrame, Shot


CANVAS = (1080, 1920)


def render_video(
    frames: list[RenderFrame],
    plan: DirectorPlan,
    output_path: Path,
    fps: int,
    target_duration: int,
) -> Path:
    if not frames:
        raise ValueError("No frames to render.")
    ffmpeg = _ffmpeg_path()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    shots = _duration_matched_shots(plan.shots, len(frames), target_duration)

    with tempfile.TemporaryDirectory(prefix="manga2anime_frames_") as tmp:
        sequence_dir = Path(tmp)
        frame_index = 1
        for render_frame, shot in zip(frames, shots, strict=False):
            image = _prepare_canvas(render_frame.path)
            frame_total = max(1, round(shot.duration * fps))
            for step in range(frame_total):
                progress = step / max(frame_total - 1, 1)
                animated = _animate(image, shot.camera_motion, progress)
                animated.save(sequence_dir / f"{frame_index:06d}.png", "PNG")
                frame_index += 1

        command = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            str(fps),
            "-i",
            str(sequence_dir / "%06d.png"),
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        subprocess.run(command, check=True)
    return output_path


def _ffmpeg_path() -> str:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # noqa: BLE001 - convert dependency detail into actionable app error.
        raise RuntimeError(
            "ffmpeg was not found on PATH and bundled imageio-ffmpeg is unavailable. "
            "Run `pip install -e .` or install ffmpeg before rendering MP4 output."
        ) from exc


def _duration_matched_shots(shots: list[Shot], frame_count: int, target_duration: int) -> list[Shot]:
    selected = shots[:frame_count]
    total = sum(shot.duration for shot in selected) or target_duration
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
        for shot in selected
    ]


def _prepare_canvas(path: Path) -> Image.Image:
    with Image.open(path) as source:
        source = ImageOps.exif_transpose(source).convert("L")
        source = ImageOps.autocontrast(source)
        source = ImageEnhance.Contrast(source).enhance(1.25)
        source = source.convert("RGB")

    canvas_ratio = CANVAS[0] / CANVAS[1]
    image_ratio = source.width / source.height
    if image_ratio > canvas_ratio:
        new_height = CANVAS[1]
        new_width = round(new_height * image_ratio)
    else:
        new_width = CANVAS[0]
        new_height = round(new_width / image_ratio)
    source = source.resize((new_width, new_height), Image.Resampling.LANCZOS)
    left = (new_width - CANVAS[0]) // 2
    top = (new_height - CANVAS[1]) // 2
    return source.crop((left, top, left + CANVAS[0], top + CANVAS[1]))


def _animate(image: Image.Image, motion: str, progress: float) -> Image.Image:
    zoom_start, zoom_end = 1.0, 1.14
    shake = motion == "impact_shake"
    if motion in {"slow_push", "zoom_in", "impact_shake"}:
        zoom = zoom_start + (zoom_end - zoom_start) * progress
    elif motion == "tilt_up":
        zoom = 1.08
    else:
        zoom = 1.05

    width, height = image.size
    zoomed = image.resize((round(width * zoom), round(height * zoom)), Image.Resampling.LANCZOS)
    max_x = zoomed.width - width
    max_y = zoomed.height - height

    if motion == "pan_left":
        x = round(max_x * (1 - progress))
        y = max_y // 2
    elif motion == "pan_right":
        x = round(max_x * progress)
        y = max_y // 2
    elif motion == "tilt_up":
        x = max_x // 2
        y = round(max_y * (1 - progress))
    else:
        x = max_x // 2
        y = max_y // 2

    if shake:
        x += round(8 * _pulse(progress))
        y += round(5 * _pulse(progress + 0.33))
        x = min(max(x, 0), max_x)
        y = min(max(y, 0), max_y)

    return zoomed.crop((x, y, x + width, y + height))


def _pulse(progress: float) -> float:
    phase = (progress * 10) % 1
    return -1.0 if phase < 0.5 else 1.0
