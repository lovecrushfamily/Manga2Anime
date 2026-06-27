from __future__ import annotations

from pathlib import Path

from manga2anime.models import DirectorPlan, Shot


def write_srt(plan: DirectorPlan, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cursor = 0.0
    blocks: list[str] = []
    for index, shot in enumerate(plan.shots, start=1):
        start = cursor
        end = cursor + max(1.0, shot.duration)
        cursor = end
        line = _shot_line(shot, index)
        blocks.append(f"{index}\n{_timestamp(start)} --> {_timestamp(end)}\n{line}\n")
    output_path.write_text("\n".join(blocks), encoding="utf-8")
    return output_path


def japanese_voice_script(plan: DirectorPlan) -> str:
    lines = [_shot_line(shot, index) for index, shot in enumerate(plan.shots, start=1)]
    return "\n".join(line for line in lines if line.strip())


def _shot_line(shot: Shot, index: int) -> str:
    voice_line = getattr(shot, "voice_line_ja", "") or getattr(shot, "subtitle_ja", "")
    if voice_line:
        return str(voice_line)
    return f"第{index}カット。{_japanese_fallback(shot.beat)}"


def _japanese_fallback(text: str) -> str:
    clean = " ".join(text.strip().split())
    if not clean:
        return "物語が静かに動き出す。"
    return f"この瞬間、{clean}"


def _timestamp(seconds: float) -> str:
    total_ms = round(seconds * 1000)
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

