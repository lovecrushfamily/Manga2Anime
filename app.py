from __future__ import annotations

import tempfile
import uuid
import mimetypes
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from manga2anime.audio import generate_japanese_voiceover, mux_audio
from manga2anime.config import AppConfig
from manga2anime.dialogue import build_dialogue_script, decode_optional_text
from manga2anime.director import build_director_plan
from manga2anime.frame_generation import generate_action_frames
from manga2anime.loader import load_chapter_uploads
from manga2anime.preprocess import build_direction_context, preprocess_pages
from manga2anime.studio import StudioService
from manga2anime.subtitles import japanese_voice_script, write_srt
from manga2anime.video import render_video


app = FastAPI(title="Manga2Anime API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@dataclass(frozen=True)
class BrowserUpload:
    name: str
    data: bytes

    def getbuffer(self) -> bytes:
        return self.data


@app.get("/api/health")
def health() -> dict:
    config = AppConfig.from_env()
    return {
        "ok": True,
        "openaiConfigured": config.has_openai_key,
        "visionModel": config.vision_model,
        "imageModel": config.image_model,
    }


def _studio_service() -> StudioService:
    return StudioService(AppConfig.from_env())


@app.post("/api/direct")
async def direct_anime(
    files: list[UploadFile] = File(...),
    subtitle_file: UploadFile | None = File(default=None),
    style_prompt: str = Form(...),
    target_duration: int = Form(20),
    max_shots: int = Form(8),
    max_pages: int = Form(20),
    use_generated_frames: bool = Form(True),
    use_voiceover: bool = Form(True),
) -> dict:
    if not files:
        raise HTTPException(status_code=400, detail="Upload one PDF or ordered manga page images.")
    if not style_prompt.strip():
        raise HTTPException(status_code=400, detail="Style prompt is required.")

    config = AppConfig.from_env()
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    uploads = [
        BrowserUpload(name=file.filename or f"upload_{index}", data=await file.read())
        for index, file in enumerate(files)
    ]
    subtitle_text = decode_optional_text(await subtitle_file.read()) if subtitle_file else None
    run_id = uuid.uuid4().hex[:12]
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory(prefix="manga2anime_") as tmp:
            work_dir = Path(tmp)
            pages = load_chapter_uploads(uploads, work_dir / "pages", max_pages=max_pages)
            dialogue_script = build_dialogue_script(pages, config, subtitle_text)
            layered_pages = preprocess_pages(pages, run_dir / "layers")
            clean_pages = [page.clean_page for page in layered_pages]
            direction_context = build_direction_context(layered_pages, dialogue_script.text)
            plan = build_director_plan(
                pages=clean_pages,
                style_prompt=style_prompt,
                config=config,
                max_shots=max_shots,
                target_duration=target_duration,
                direction_context=direction_context,
            )
            frames = generate_action_frames(
                pages=clean_pages,
                plan=plan,
                style_prompt=style_prompt,
                config=config,
                output_dir=run_dir / "generated",
                enabled=use_generated_frames and config.has_openai_key,
                character_references={page.index: page.character_path for page in layered_pages},
            )
            video_path = render_video(
                frames=frames,
                plan=plan,
                output_path=run_dir / f"manga2anime_{run_id}.mp4",
                fps=config.fps,
                target_duration=target_duration,
            )
            subtitle_path = write_srt(plan, run_dir / f"manga2anime_{run_id}.ja.srt")
            voice_script = japanese_voice_script(plan)
            voice_line_count = sum(1 for line in voice_script.splitlines() if line.strip())
            voice_path, voice_source = generate_japanese_voiceover(
                voice_script,
                config,
                run_dir / f"manga2anime_{run_id}.voice.mp3",
            ) if use_voiceover else (None, "disabled")
            final_video_path = mux_audio(
                video_path,
                voice_path,
                run_dir / f"manga2anime_{run_id}.final.mp4",
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - API should convert pipeline failures into JSON.
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "runId": run_id,
        "videoUrl": f"/api/video/{run_id}/{final_video_path.name}",
        "subtitleUrl": f"/api/subtitle/{run_id}/{subtitle_path.name}",
        "voiceoverUrl": f"/api/audio/{run_id}/{voice_path.name}" if voice_path else None,
        "voiceoverSource": voice_source,
        "hasAudio": final_video_path != video_path,
        "japaneseDubbing": {
            "language": "Japanese",
            "voice": config.tts_voice,
            "model": config.tts_model,
            "status": voice_source,
            "lineCount": voice_line_count,
            "mixed": final_video_path != video_path,
        },
        "plan": plan.to_dict(),
        "generatedFrameCount": sum(1 for frame in frames if frame.generated),
        "sourceFrameCount": sum(1 for frame in frames if not frame.generated),
        "preprocess": {
            "layeredPageCount": len(layered_pages),
            "dialogueRegionsRemoved": sum(len(page.dialogue_regions) for page in layered_pages),
            "dialogueSource": dialogue_script.source,
            "dialogueCueCount": dialogue_script.cue_count,
            "motionHints": [page.motion_hint for page in layered_pages],
        },
        "openaiConfigured": config.has_openai_key,
    }


@app.post("/api/studio/jobs")
async def create_studio_job(
    files: list[UploadFile] = File(...),
    subtitle_file: UploadFile | None = File(default=None),
    style_prompt: str = Form(...),
    target_duration: int = Form(20),
    max_pages: int = Form(20),
    quality: str = Form("high"),
    use_generated_frames: bool = Form(True),
    use_voiceover: bool = Form(True),
) -> dict:
    try:
        uploads = [
            (file.filename or f"upload_{index}", await file.read())
            for index, file in enumerate(files)
        ]
        subtitle_text = decode_optional_text(await subtitle_file.read()) if subtitle_file else None
        return _studio_service().create_job(
            uploads=uploads,
            subtitle_text=subtitle_text,
            settings={
                "style_prompt": style_prompt,
                "target_duration": target_duration,
                "max_pages": max_pages,
                "quality": quality,
                "use_generated_frames": use_generated_frames,
                "use_voiceover": use_voiceover,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - keep frontend failures JSON-shaped.
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/studio/jobs/{job_id}")
def get_studio_job(job_id: str) -> dict:
    try:
        return _studio_service().get_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Studio job not found.") from exc


@app.post("/api/studio/jobs/{job_id}/stages/{stage}/run")
def run_studio_stage(job_id: str, stage: str, segment_id: str | None = None) -> dict:
    try:
        return _studio_service().run_stage(job_id, stage, segment_id=segment_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Studio job not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - stage failures should be visible in the UI.
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/studio/jobs/{job_id}/assets/{asset_id}/approve")
def approve_studio_asset(job_id: str, asset_id: str, notes: str | None = Form(default=None)) -> dict:
    try:
        return _studio_service().approve_asset(job_id, asset_id, notes=notes)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Studio job not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/studio/jobs/{job_id}/assets/{asset_id}/reject")
def reject_studio_asset(job_id: str, asset_id: str, notes: str | None = Form(default=None)) -> dict:
    try:
        return _studio_service().reject_asset(job_id, asset_id, notes=notes)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Studio job not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/studio/jobs/{job_id}/assets/{asset_id}/regenerate")
def regenerate_studio_asset(job_id: str, asset_id: str, notes: str | None = Form(default=None)) -> dict:
    try:
        return _studio_service().regenerate_asset(job_id, asset_id, notes=notes)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Studio job not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - regeneration can fail on external model calls.
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/studio/jobs/{job_id}/finalize")
def finalize_studio_job(job_id: str) -> dict:
    try:
        return _studio_service().finalize(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Studio job not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - render/mux failures should be surfaced.
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/studio/jobs/{job_id}/files/{relative_path:path}")
def studio_file(job_id: str, relative_path: str) -> FileResponse:
    try:
        path = _studio_service().file_path(job_id, relative_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Studio asset not found.") from exc
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name)


@app.get("/api/video/{run_id}/{filename}")
def video(run_id: str, filename: str) -> FileResponse:
    safe_run_id = Path(run_id).name
    safe_name = Path(filename).name
    path = Path(AppConfig.from_env().output_dir) / safe_run_id / safe_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Video not found.")
    return FileResponse(path, media_type="video/mp4", filename=safe_name)


@app.get("/api/subtitle/{run_id}/{filename}")
def subtitle(run_id: str, filename: str) -> FileResponse:
    safe_run_id = Path(run_id).name
    safe_name = Path(filename).name
    path = Path(AppConfig.from_env().output_dir) / safe_run_id / safe_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Subtitle not found.")
    return FileResponse(path, media_type="application/x-subrip", filename=safe_name)


@app.get("/api/audio/{run_id}/{filename}")
def audio(run_id: str, filename: str) -> FileResponse:
    safe_run_id = Path(run_id).name
    safe_name = Path(filename).name
    path = Path(AppConfig.from_env().output_dir) / safe_run_id / safe_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio not found.")
    return FileResponse(path, media_type="audio/mpeg", filename=safe_name)
