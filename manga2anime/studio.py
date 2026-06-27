from __future__ import annotations

import json
import math
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openai import OpenAI
from PIL import Image, ImageDraw, ImageOps

from manga2anime.audio import generate_japanese_voiceover, mux_audio
from manga2anime.config import AppConfig
from manga2anime.dialogue import build_dialogue_script
from manga2anime.director import CAMERA_MOTIONS
from manga2anime.frame_generation import generate_studio_image_asset
from manga2anime.loader import load_chapter_uploads
from manga2anime.models import (
    CoverageManifest,
    GeneratedAsset,
    PageAsset,
    PageImage,
    QCReport,
    RenderFrame,
    SceneSegment,
    Shot,
)
from manga2anime.openai_utils import extract_output_text, image_to_data_url
from manga2anime.preprocess import build_direction_context, preprocess_pages
from manga2anime.style import build_style_directive
from manga2anime.subtitles import japanese_voice_script, write_srt
from manga2anime.video import render_video


STUDIO_STAGES = [
    "ingest",
    "page_analysis",
    "storyboard",
    "character_bible",
    "segment_keyframes",
    "segment_inbetweens",
    "audio",
    "final_cut",
]


@dataclass(frozen=True)
class SavedUpload:
    name: str
    path: Path

    def getbuffer(self) -> bytes:
        return self.path.read_bytes()


class StudioService:
    def __init__(self, config: AppConfig):
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_job(
        self,
        uploads: list[tuple[str, bytes]],
        subtitle_text: str | None,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        if not uploads:
            raise ValueError("Upload one PDF or ordered manga page images.")
        if not str(settings.get("style_prompt", "")).strip():
            raise ValueError("Style prompt is required.")

        job_id = uuid.uuid4().hex[:12]
        run_dir = self._run_dir(job_id)
        upload_dir = run_dir / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)

        saved_uploads: list[dict[str, Any]] = []
        for index, (name, data) in enumerate(uploads, start=1):
            safe_name = f"upload_{index:03d}_{Path(name or f'page_{index}').name}"
            upload_path = upload_dir / safe_name
            upload_path.write_bytes(data)
            saved_uploads.append(
                {
                    "index": index,
                    "original_name": name,
                    "saved_name": safe_name,
                    "path": self._relative(job_id, upload_path),
                    "size": len(data),
                }
            )

        if subtitle_text:
            (run_dir / "subtitle_source.txt").write_text(subtitle_text, encoding="utf-8")

        now = _now()
        job = {
            "id": job_id,
            "status": "pending",
            "active_stage": "ingest",
            "created_at": now,
            "updated_at": now,
            "settings": {
                "style_prompt": str(settings.get("style_prompt", "")).strip(),
                "target_duration": int(settings.get("target_duration", 20)),
                "max_pages": int(settings.get("max_pages", self.config.max_pages)),
                "quality": str(settings.get("quality", "high")).lower(),
                "use_generated_frames": bool(settings.get("use_generated_frames", True)),
                "use_voiceover": bool(settings.get("use_voiceover", True)),
            },
            "stages": {
                stage: {
                    "id": stage,
                    "status": "pending",
                    "summary": "Waiting",
                    "updated_at": now,
                }
                for stage in STUDIO_STAGES
            },
            "uploads": saved_uploads,
            "pages": [],
            "page_analysis": [],
            "coverage_manifest": None,
            "segments": [],
            "assets": [],
            "dialogue": {
                "text": subtitle_text or "",
                "source": "subtitle_upload" if subtitle_text else "none",
                "cue_count": 0,
            },
            "final_outputs": {},
            "messages": ["Studio job created. Run ingest to normalize uploaded pages."],
        }
        self._save(job)
        return self._hydrate(job)

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self._hydrate(self._load(job_id))

    def run_stage(self, job_id: str, stage: str, segment_id: str | None = None) -> dict[str, Any]:
        if stage not in STUDIO_STAGES:
            raise ValueError(f"Unknown studio stage: {stage}")
        job = self._load(job_id)
        self._set_stage(job, stage, "running", "Running")
        job["status"] = "running"
        job["active_stage"] = stage
        self._save(job)

        try:
            {
                "ingest": self._run_ingest,
                "page_analysis": self._run_page_analysis,
                "storyboard": self._run_storyboard,
                "character_bible": self._run_character_bible,
                "segment_keyframes": self._run_segment_keyframes,
                "segment_inbetweens": self._run_segment_inbetweens,
                "audio": self._run_audio,
                "final_cut": self._run_final_cut_marker,
            }[stage](job, segment_id)
        except Exception as exc:
            self._set_stage(job, stage, "failed", str(exc))
            job["status"] = "failed"
            self._message(job, f"{stage} failed: {exc}")
            self._save(job)
            raise

        job["status"] = "needs_review"
        job["updated_at"] = _now()
        self._save(job)
        return self._hydrate(job)

    def approve_asset(self, job_id: str, asset_id: str, notes: str | None = None) -> dict[str, Any]:
        job = self._load(job_id)
        asset = self._require_asset(job, asset_id)
        asset["status"] = "approved"
        if notes:
            asset.setdefault("notes", []).append(notes)
        self._sync_segment_status(job, asset.get("segment_id"))
        self._message(job, f"Approved {asset_id}.")
        job["updated_at"] = _now()
        self._save(job)
        return self._hydrate(job)

    def reject_asset(self, job_id: str, asset_id: str, notes: str | None = None) -> dict[str, Any]:
        job = self._load(job_id)
        asset = self._require_asset(job, asset_id)
        asset["status"] = "rejected"
        if notes:
            asset.setdefault("notes", []).append(notes)
        self._sync_segment_status(job, asset.get("segment_id"))
        self._message(job, f"Rejected {asset_id}.")
        job["updated_at"] = _now()
        self._save(job)
        return self._hydrate(job)

    def regenerate_asset(self, job_id: str, asset_id: str, notes: str | None = None) -> dict[str, Any]:
        job = self._load(job_id)
        asset = self._require_asset(job, asset_id)
        kind = asset["kind"]
        if kind not in {"keyframe_start", "keyframe_end", "transition", "storyboard"}:
            raise ValueError(f"Regeneration is not supported yet for {kind} assets.")

        asset["status"] = "rejected"
        asset.setdefault("notes", []).append(notes or "Superseded by a regenerated version.")
        lineage_id = asset.get("lineage_id") or asset["id"]
        next_version = 1 + max(
            int(candidate.get("version", 1))
            for candidate in job["assets"]
            if (candidate.get("lineage_id") or candidate.get("id")) == lineage_id
        )

        if kind == "storyboard":
            new_asset = dict(asset)
            new_asset["id"] = f"{lineage_id}_v{next_version}"
            new_asset["version"] = next_version
            new_asset["status"] = "needs_review"
            new_asset["lineage_id"] = lineage_id
            new_asset["created_at"] = _now()
            new_asset.setdefault("notes", []).append(notes or "Regenerated storyboard review copy.")
            job["assets"].append(new_asset)
        else:
            segment = self._require_segment(job, str(asset["segment_id"]))
            new_asset = self._generate_segment_image_asset(
                job=job,
                segment=segment,
                kind=kind,
                version=next_version,
                frame_index=asset.get("metadata", {}).get("frame_index"),
                lineage_id=lineage_id,
                user_notes=notes,
            )
            job["assets"].append(new_asset)

        self._sync_segment_status(job, asset.get("segment_id"))
        self._message(job, f"Regenerated {asset_id} as version {next_version}.")
        job["updated_at"] = _now()
        self._save(job)
        return self._hydrate(job)

    def file_path(self, job_id: str, relative_path: str) -> Path:
        run_dir = self._run_dir(job_id).resolve()
        path = (run_dir / relative_path).resolve()
        if not path.is_relative_to(run_dir) or not path.exists():
            raise FileNotFoundError(relative_path)
        return path

    def _run_ingest(self, job: dict[str, Any], segment_id: str | None = None) -> None:
        del segment_id
        job_id = job["id"]
        upload_dir = self._run_dir(job_id) / "uploads"
        saved_uploads = [
            SavedUpload(name=upload["saved_name"], path=upload_dir / upload["saved_name"])
            for upload in job["uploads"]
        ]
        pages = load_chapter_uploads(
            saved_uploads,
            self._run_dir(job_id) / "normalized_pages",
            max_pages=int(job["settings"]["max_pages"]),
        )
        subtitle_text = self._subtitle_source_text(job_id)
        dialogue_script = build_dialogue_script(pages, self.config, subtitle_text)
        layered_pages = preprocess_pages(pages, self._run_dir(job_id) / "layers")
        page_assets = [
            PageAsset(
                index=page.index,
                original_path=self._relative(job_id, page.original_page.path),
                clean_path=self._relative(job_id, page.clean_page.path),
                background_path=self._relative(job_id, page.background_path),
                character_path=self._relative(job_id, page.character_path),
                width=page.clean_page.width,
                height=page.clean_page.height,
                dialogue_regions=page.dialogue_regions,
                motion_hint=page.motion_hint,
            ).to_dict()
            for page in layered_pages
        ]
        job["pages"] = page_assets
        job["dialogue"] = {
            "text": dialogue_script.text,
            "source": dialogue_script.source,
            "cue_count": dialogue_script.cue_count,
        }
        job["direction_context"] = build_direction_context(layered_pages, dialogue_script.text)
        self._set_stage(
            job,
            "ingest",
            "complete",
            f"{len(page_assets)} pages normalized; {sum(len(p['dialogue_regions']) for p in page_assets)} text regions removed.",
        )
        self._message(job, f"Ingest completed with {len(page_assets)} page(s).")

    def _run_page_analysis(self, job: dict[str, Any], segment_id: str | None = None) -> None:
        del segment_id
        self._require_pages(job)
        pages = self._page_images(job)
        analyses: list[dict[str, Any]] = []
        for batch_start in range(0, len(pages), 4):
            batch = pages[batch_start : batch_start + 4]
            analyses.extend(self._analyze_pages_batch(job, batch))
        page_by_index = {page["index"]: page for page in job["pages"]}
        for analysis in analyses:
            page = page_by_index.get(int(analysis["page_index"]))
            if page is not None:
                page["analysis"] = analysis
        job["page_analysis"] = analyses
        self._set_stage(job, "page_analysis", "complete", f"Analyzed all {len(analyses)} page(s).")
        self._message(job, "Page Analyst covered every uploaded page.")

    def _run_storyboard(self, job: dict[str, Any], segment_id: str | None = None) -> None:
        del segment_id
        self._require_pages(job)
        if not job.get("page_analysis"):
            self._run_page_analysis(job)

        page_indexes = [int(page["index"]) for page in job["pages"]]
        duration = int(job["settings"]["target_duration"])
        page_pairs = [page_indexes[index : index + 2] for index in range(0, len(page_indexes), 2)]
        segment_duration = duration / max(1, len(page_pairs))
        analysis_by_page = {int(item["page_index"]): item for item in job.get("page_analysis", [])}

        segments: list[dict[str, Any]] = []
        coverage: dict[str, list[str]] = {str(index): [] for index in page_indexes}
        for index, pages in enumerate(page_pairs, start=1):
            segment_id_value = f"seg_{index:03d}"
            summaries = [analysis_by_page.get(page, {}).get("summary", f"page {page}") for page in pages]
            beat = " / ".join(str(summary) for summary in summaries)
            motion = CAMERA_MOTIONS[(index - 1) % len(CAMERA_MOTIONS)]
            segment = SceneSegment(
                id=segment_id_value,
                index=index,
                page_indexes=pages,
                title=f"Scene {index:02d}",
                beat=f"Adapt pages {', '.join(map(str, pages))}: {beat}",
                duration=round(segment_duration, 2),
                camera_motion=motion,
                transition="ink-smear continuity cut",
                start_prompt=self._segment_prompt(pages, beat, "opening keyframe"),
                end_prompt=self._segment_prompt(pages, beat, "closing keyframe"),
                subtitle_ja=f"第{index}場面。物語が前へ進む。",
                voice_line_ja=f"第{index}場面。物語が前へ進む。",
                status="needs_review",
            ).to_dict()
            segments.append(segment)
            for page in pages:
                coverage[str(page)].append(segment_id_value)

        manifest = CoverageManifest(
            total_pages=len(page_indexes),
            covered_pages=page_indexes,
            page_to_segments=coverage,
            omitted_pages=[],
        ).to_dict()
        job["segments"] = segments
        job["coverage_manifest"] = manifest
        job["assets"] = [
            asset
            for asset in job["assets"]
            if asset["kind"] not in {"storyboard", "keyframe_start", "keyframe_end", "transition"}
        ]
        for segment in segments:
            job["assets"].append(
                GeneratedAsset(
                    id=f"{segment['id']}_storyboard",
                    segment_id=segment["id"],
                    kind="storyboard",
                    version=1,
                    status="needs_review",
                    source_pages=segment["page_indexes"],
                    prompt=segment["beat"],
                    qc=QCReport(
                        status="pass",
                        score=1.0,
                        checks={"all_pages_mapped": True, "dialogue_off_frame": True},
                        notes=["Storyboard uses uploaded page order and requires human approval."],
                    ).to_dict(),
                    created_at=_now(),
                ).to_dict()
            )
        self._set_stage(job, "storyboard", "needs_review", f"{len(segments)} scenes cover {len(page_indexes)}/{len(page_indexes)} pages.")
        self._message(job, f"Storyboard created with {len(segments)} scene(s); approve scenes before keyframes.")

    def _run_character_bible(self, job: dict[str, Any], segment_id: str | None = None) -> None:
        del segment_id
        self._require_pages(job)
        bible_dir = self._run_dir(job["id"]) / "character_bible"
        bible_dir.mkdir(parents=True, exist_ok=True)
        bible_path = bible_dir / "character_bible.png"
        self._build_character_contact_sheet(job, bible_path)
        existing = self._assets_by_kind(job, "character_bible")
        if existing:
            existing[-1]["path"] = self._relative(job["id"], bible_path)
            existing[-1]["url"] = self._url(job["id"], bible_path)
            existing[-1]["status"] = "needs_review"
        else:
            job["assets"].append(
                GeneratedAsset(
                    id="character_bible",
                    segment_id=None,
                    kind="character_bible",
                    version=1,
                    status="needs_review",
                    source_pages=[int(page["index"]) for page in job["pages"]],
                    prompt="Canonical character model contact sheet from all uploaded pages.",
                    path=self._relative(job["id"], bible_path),
                    url=self._url(job["id"], bible_path),
                    generated=False,
                    qc=QCReport(
                        status="pass",
                        score=1.0,
                        checks={"uses_all_pages": True, "has_visual_reference": True},
                        notes=["Approve this before generated keyframes so the face model is locked."],
                    ).to_dict(),
                    created_at=_now(),
                ).to_dict()
            )
        self._set_stage(job, "character_bible", "needs_review", "Character bible contact sheet ready for approval.")
        self._message(job, "Character Bible Artist prepared the model reference sheet.")

    def _run_segment_keyframes(self, job: dict[str, Any], segment_id: str | None = None) -> None:
        self._require_storyboard(job)
        self._require_character_bible_approved(job)
        segment = self._selected_segment(job, segment_id, require_storyboard_approval=True)
        if not segment:
            self._set_stage(job, "segment_keyframes", "needs_review", "Approve a storyboard scene before generating keyframes.")
            return

        for kind in ("keyframe_start", "keyframe_end"):
            if self._latest_asset(job, segment["id"], kind, statuses={"needs_review", "approved"}):
                continue
            job["assets"].append(
                self._generate_segment_image_asset(job, segment, kind, version=1, frame_index=None)
            )
        self._set_stage(job, "segment_keyframes", "needs_review", f"Keyframes ready for {segment['title']}.")
        self._message(job, f"Generated two keyframes for {segment['id']}; approve both before transitions.")

    def _run_segment_inbetweens(self, job: dict[str, Any], segment_id: str | None = None) -> None:
        self._require_storyboard(job)
        segment = self._selected_segment(job, segment_id, require_storyboard_approval=True)
        if not segment:
            self._set_stage(job, "segment_inbetweens", "needs_review", "Approve a storyboard scene before generating transitions.")
            return
        start = self._latest_asset(job, segment["id"], "keyframe_start", statuses={"approved"})
        end = self._latest_asset(job, segment["id"], "keyframe_end", statuses={"approved"})
        if not start or not end:
            self._set_stage(job, "segment_inbetweens", "needs_review", "Approve both keyframes before in-between generation.")
            return

        target_count = self._transition_count(job)
        existing_indexes = {
            int(asset.get("metadata", {}).get("frame_index", 0))
            for asset in self._assets_for_segment(job, segment["id"], "transition")
            if asset["status"] in {"needs_review", "approved"}
        }
        for frame_index in range(1, target_count + 1):
            if frame_index in existing_indexes:
                continue
            job["assets"].append(
                self._generate_segment_image_asset(
                    job,
                    segment,
                    "transition",
                    version=1,
                    frame_index=frame_index,
                )
            )
        self._set_stage(job, "segment_inbetweens", "needs_review", f"{target_count} transition frames ready for {segment['title']}.")
        self._message(job, f"Generated transition frames for {segment['id']}.")

    def _run_audio(self, job: dict[str, Any], segment_id: str | None = None) -> None:
        del segment_id
        self._require_storyboard(job)
        plan = self._segments_director_plan(job)
        run_dir = self._run_dir(job["id"])
        subtitle_path = write_srt(plan, run_dir / f"manga2anime_{job['id']}.ja.srt")
        self._upsert_system_asset(
            job,
            kind="subtitle",
            path=subtitle_path,
            prompt="Japanese subtitle timing outside the artwork.",
            source_pages=[page for segment in job["segments"] for page in segment["page_indexes"]],
        )

        if bool(job["settings"].get("use_voiceover", True)):
            voice_script = japanese_voice_script(plan)
            voice_path, voice_source = generate_japanese_voiceover(
                voice_script,
                self.config,
                run_dir / f"manga2anime_{job['id']}.voice.mp3",
            )
            if voice_path:
                self._upsert_system_asset(
                    job,
                    kind="voice",
                    path=voice_path,
                    prompt=f"Japanese voiceover generated by {voice_source}.",
                    source_pages=[],
                )
            else:
                self._message(job, f"Voice Director could not create MP3: {voice_source}.")
        self._set_stage(job, "audio", "needs_review", "Subtitle and voice assets are ready for review.")
        self._message(job, "Dialogue Adapter prepared off-frame Japanese dialogue assets.")

    def _run_final_cut_marker(self, job: dict[str, Any], segment_id: str | None = None) -> None:
        del segment_id
        readiness = self._finalize_readiness(job)
        status = "complete" if readiness["ready"] else "needs_review"
        self._set_stage(job, "final_cut", status, readiness["summary"])

    def finalize(self, job_id: str) -> dict[str, Any]:
        job = self._load(job_id)
        readiness = self._finalize_readiness(job)
        if not readiness["ready"]:
            raise ValueError(readiness["summary"])

        render_frames: list[RenderFrame] = []
        render_shots: list[Shot] = []
        for segment in job["segments"]:
            image_assets = self._approved_visual_assets_for_segment(job, segment["id"])
            duration = float(segment["duration"]) / max(1, len(image_assets))
            for asset in image_assets:
                path = self._run_dir(job_id) / asset["path"]
                render_frames.append(
                    RenderFrame(
                        path=path,
                        source_page=int(asset["source_pages"][0]) if asset["source_pages"] else 1,
                        generated=bool(asset.get("generated")),
                    )
                )
                render_shots.append(
                    Shot(
                        source_page=int(asset["source_pages"][0]) if asset["source_pages"] else 1,
                        beat=segment["beat"],
                        camera_motion=segment["camera_motion"],
                        transition=segment["transition"],
                        duration=duration,
                        frame_prompt=asset["prompt"],
                        animation_notes="Frame-level approved studio asset.",
                        subtitle_ja=segment.get("subtitle_ja", ""),
                        voice_line_ja=segment.get("voice_line_ja", ""),
                    )
                )

        run_dir = self._run_dir(job_id)
        target_duration = int(job["settings"]["target_duration"])
        render_plan = self._segments_director_plan(job, render_shots)
        base_video = render_video(
            render_frames,
            render_plan,
            run_dir / f"manga2anime_{job_id}.studio.mp4",
            fps=self.config.fps,
            target_duration=target_duration,
        )
        subtitle_asset = self._latest_asset(job, None, "subtitle", statuses={"approved"})
        if not subtitle_asset:
            subtitle_path = write_srt(self._segments_director_plan(job), run_dir / f"manga2anime_{job_id}.ja.srt")
        else:
            subtitle_path = run_dir / subtitle_asset["path"]
        voice_asset = self._latest_asset(job, None, "voice", statuses={"approved"})
        voice_path = run_dir / voice_asset["path"] if voice_asset else None
        final_video = mux_audio(base_video, voice_path, run_dir / f"manga2anime_{job_id}.final.mp4")
        final_asset = GeneratedAsset(
            id="final_video",
            segment_id=None,
            kind="final_video",
            version=1,
            status="needs_review",
            source_pages=[int(page["index"]) for page in job["pages"]],
            prompt="Final studio cut from approved scene assets.",
            path=self._relative(job_id, final_video),
            url=self._url(job_id, final_video),
            generated=False,
            qc=QCReport(
                status="pass",
                score=1.0,
                checks={
                    "coverage_complete": True,
                    "all_required_assets_approved": True,
                    "dialogue_off_frame": True,
                },
                notes=["Final cut assembled from approved keyframes and transition frames."],
            ).to_dict(),
            created_at=_now(),
        ).to_dict()
        job["assets"] = [asset for asset in job["assets"] if asset["kind"] != "final_video"]
        job["assets"].append(final_asset)
        job["final_outputs"] = {
            "videoUrl": self._url(job_id, final_video),
            "subtitleUrl": self._url(job_id, subtitle_path),
            "voiceoverUrl": self._url(job_id, voice_path) if voice_path else None,
            "hasAudio": final_video != base_video,
        }
        job["status"] = "needs_review"
        self._set_stage(job, "final_cut", "needs_review", "Final cut rendered from approved assets.")
        self._message(job, "Final studio cut is ready for preview.")
        job["updated_at"] = _now()
        self._save(job)
        return self._hydrate(job)

    def _analyze_pages_batch(self, job: dict[str, Any], pages: list[PageImage]) -> list[dict[str, Any]]:
        if self.config.has_openai_key:
            try:
                client = OpenAI(api_key=self.config.openai_api_key)
                content: list[dict[str, Any]] = [
                    {
                        "type": "input_text",
                        "text": (
                            "You are the Page Analyst in a manga-to-anime studio. Analyze every uploaded "
                            "page in this batch. Return JSON only: {\"pages\": [{\"page_index\": number, "
                            "\"summary\": string, \"characters\": [string], \"action\": string, "
                            "\"camera_hint\": string, \"dialogue_hint\": string}]}. Do not omit any page."
                        ),
                    }
                ]
                for page in pages:
                    content.append({"type": "input_text", "text": f"page_index={page.index}"})
                    content.append({"type": "input_image", "image_url": image_to_data_url(page.path)})
                response = client.responses.create(
                    model=self.config.vision_model,
                    input=[{"role": "user", "content": content}],
                )
                payload = _parse_json(extract_output_text(response))
                parsed = payload.get("pages") if isinstance(payload, dict) else []
                if isinstance(parsed, list) and len(parsed) == len(pages):
                    return [self._normalize_page_analysis(page, raw) for page, raw in zip(pages, parsed, strict=False)]
            except Exception as exc:  # noqa: BLE001 - fallback keeps all pages covered.
                self._message(job, f"Page Analyst fallback used: {type(exc).__name__}.")
        return [self._fallback_page_analysis(page, job) for page in pages]

    def _normalize_page_analysis(self, page: PageImage, raw: Any) -> dict[str, Any]:
        raw = raw if isinstance(raw, dict) else {}
        return {
            "page_index": page.index,
            "summary": str(raw.get("summary") or f"Story beat from page {page.index}"),
            "characters": [str(item) for item in raw.get("characters", [])[:8]] if isinstance(raw.get("characters"), list) else [],
            "action": str(raw.get("action") or "panel motion and emotional beat"),
            "camera_hint": str(raw.get("camera_hint") or "slow_push"),
            "dialogue_hint": str(raw.get("dialogue_hint") or "keep dialogue off-frame"),
        }

    def _fallback_page_analysis(self, page: PageImage, job: dict[str, Any]) -> dict[str, Any]:
        page_meta = next((item for item in job["pages"] if int(item["index"]) == page.index), {})
        return {
            "page_index": page.index,
            "summary": f"Page {page.index} manga beat with {page_meta.get('motion_hint', 'camera motion')}",
            "characters": ["source manga character model"],
            "action": str(page_meta.get("motion_hint", "panel-to-panel motion")),
            "camera_hint": str(page_meta.get("motion_hint", "slow_push")),
            "dialogue_hint": "dialogue metadata stays outside generated frames",
        }

    def _generate_segment_image_asset(
        self,
        job: dict[str, Any],
        segment: dict[str, Any],
        kind: str,
        version: int,
        frame_index: int | None,
        lineage_id: str | None = None,
        user_notes: str | None = None,
    ) -> dict[str, Any]:
        job_id = job["id"]
        source_page_index = self._source_page_for_kind(job, segment, kind, frame_index)
        source = self._page_image(job, source_page_index)
        character_reference = self._character_reference(job, source_page_index)
        reference_paths = self._reference_paths_for_transition(job, segment["id"], kind)
        asset_stem = self._asset_stem(segment["id"], kind, frame_index)
        asset_id = f"{asset_stem}_v{version}" if version > 1 else asset_stem
        output_path = self._run_dir(job_id) / "assets" / segment["id"] / f"{asset_id}.png"
        prompt = self._prompt_for_asset(job, segment, kind, frame_index, user_notes)
        generated = generate_studio_image_asset(
            source=source,
            character_reference=character_reference,
            reference_paths=reference_paths,
            frame_prompt=prompt,
            style_directive=build_style_directive(job["settings"]["style_prompt"]),
            style_prompt=job["settings"]["style_prompt"],
            config=self.config,
            output_path=output_path,
            enabled=bool(job["settings"].get("use_generated_frames", True)),
        )
        return GeneratedAsset(
            id=asset_id,
            segment_id=segment["id"],
            kind=kind,
            version=version,
            status="needs_review",
            source_pages=list(segment["page_indexes"]),
            prompt=prompt,
            path=self._relative(job_id, output_path),
            url=self._url(job_id, output_path),
            generated=generated,
            qc=self._qc_image(output_path, generated, source_page_index).to_dict(),
            notes=[user_notes] if user_notes else [],
            metadata={"frame_index": frame_index} if frame_index is not None else {},
            lineage_id=lineage_id,
            created_at=_now(),
        ).to_dict()

    def _qc_image(self, path: Path, generated: bool, source_page_index: int) -> QCReport:
        checks = {
            "file_exists": path.exists(),
            "source_reference_present": source_page_index > 0,
            "dialogue_off_frame_prompted": True,
            "identity_reference_prompted": True,
            "generated_or_source_fallback": generated or path.exists(),
        }
        notes: list[str] = []
        status = "pass"
        score = 1.0
        if path.exists():
            with Image.open(path) as image:
                checks["minimum_resolution"] = image.width >= 512 and image.height >= 512
                if not checks["minimum_resolution"]:
                    notes.append("Frame is below the preferred review resolution.")
                    status = "warning"
                    score = 0.82
        else:
            status = "fail"
            score = 0.0
            notes.append("Frame file was not created.")
        if not generated:
            notes.append("Source fallback used; identity is safer but motion may be limited.")
            score = min(score, 0.9)
        return QCReport(status=status, score=score, checks=checks, notes=notes)

    def _upsert_system_asset(
        self,
        job: dict[str, Any],
        kind: str,
        path: Path,
        prompt: str,
        source_pages: list[int],
    ) -> None:
        existing = self._assets_by_kind(job, kind)
        payload = GeneratedAsset(
            id=kind,
            segment_id=None,
            kind=kind,
            version=(existing[-1]["version"] + 1) if existing else 1,
            status="needs_review",
            source_pages=source_pages,
            prompt=prompt,
            path=self._relative(job["id"], path),
            url=self._url(job["id"], path),
            generated=False,
            qc=QCReport(
                status="pass",
                score=1.0,
                checks={"file_exists": path.exists(), "off_frame_dialogue": True},
                notes=["Human approval required before final cut."],
            ).to_dict(),
            created_at=_now(),
        ).to_dict()
        job["assets"] = [asset for asset in job["assets"] if asset["kind"] != kind]
        job["assets"].append(payload)

    def _build_character_contact_sheet(self, job: dict[str, Any], output_path: Path) -> None:
        references = [self._run_dir(job["id"]) / page["character_path"] for page in job["pages"]]
        thumb_w, thumb_h = 300, 420
        columns = min(4, max(1, len(references)))
        rows = math.ceil(len(references) / columns)
        sheet = Image.new("RGB", (columns * thumb_w, rows * (thumb_h + 44)), "white")
        draw = ImageDraw.Draw(sheet)
        for index, reference in enumerate(references):
            x = (index % columns) * thumb_w
            y = (index // columns) * (thumb_h + 44)
            with Image.open(reference) as image:
                image = ImageOps.exif_transpose(image).convert("RGBA")
                image.thumbnail((thumb_w - 28, thumb_h - 28), Image.Resampling.LANCZOS)
                backdrop = Image.new("RGBA", (thumb_w, thumb_h), (255, 255, 255, 255))
                left = (thumb_w - image.width) // 2
                top = (thumb_h - image.height) // 2
                backdrop.alpha_composite(image, (left, top))
                sheet.paste(backdrop.convert("RGB"), (x, y))
            draw.text((x + 16, y + thumb_h + 12), f"page {job['pages'][index]['index']}", fill=(20, 20, 20))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(output_path, "PNG")

    def _finalize_readiness(self, job: dict[str, Any]) -> dict[str, Any]:
        missing: list[str] = []
        manifest = job.get("coverage_manifest") or {}
        if not manifest.get("complete"):
            missing.append("coverage manifest is not complete")
        if not self._latest_asset(job, None, "character_bible", statuses={"approved"}):
            missing.append("character bible is not approved")
        for segment in job.get("segments", []):
            if not self._latest_asset(job, segment["id"], "storyboard", statuses={"approved"}):
                missing.append(f"{segment['id']} storyboard is not approved")
            for kind in ("keyframe_start", "keyframe_end"):
                if not self._latest_asset(job, segment["id"], kind, statuses={"approved"}):
                    missing.append(f"{segment['id']} {kind} is not approved")
            transitions = [
                asset
                for asset in self._assets_for_segment(job, segment["id"], "transition")
                if asset["status"] == "approved"
            ]
            if len(transitions) < self._transition_count(job):
                missing.append(f"{segment['id']} needs {self._transition_count(job)} approved transition frames")
        if not self._latest_asset(job, None, "subtitle", statuses={"approved"}):
            missing.append("subtitle asset is not approved")
        return {
            "ready": not missing,
            "missing": missing,
            "summary": "Ready for final cut." if not missing else "; ".join(missing[:6]),
        }

    def _approved_visual_assets_for_segment(self, job: dict[str, Any], segment_id: str) -> list[dict[str, Any]]:
        start = self._latest_asset(job, segment_id, "keyframe_start", statuses={"approved"})
        end = self._latest_asset(job, segment_id, "keyframe_end", statuses={"approved"})
        transitions = sorted(
            [
                asset
                for asset in self._assets_for_segment(job, segment_id, "transition")
                if asset["status"] == "approved"
            ],
            key=lambda item: int(item.get("metadata", {}).get("frame_index", 0)),
        )
        return [asset for asset in [start, *transitions, end] if asset]

    def _segments_director_plan(self, job: dict[str, Any], shots: list[Shot] | None = None):
        from manga2anime.models import DirectorPlan

        if shots is None:
            shots = [
                Shot(
                    source_page=int(segment["page_indexes"][0]),
                    beat=segment["beat"],
                    camera_motion=segment["camera_motion"],
                    transition=segment["transition"],
                    duration=float(segment["duration"]),
                    frame_prompt=segment["start_prompt"],
                    animation_notes="Approved studio segment.",
                    subtitle_ja=segment.get("subtitle_ja", ""),
                    voice_line_ja=segment.get("voice_line_ja", ""),
                )
                for segment in job["segments"]
            ]
        return DirectorPlan(
            chapter_summary=f"Studio production cut from {len(job['pages'])} uploaded manga page(s).",
            style_directive=build_style_directive(job["settings"]["style_prompt"]),
            studio_roles={
                "director": "Owns story coverage, pacing, and approval gates.",
                "page_analyst": "Analyzes every uploaded page before storyboard.",
                "character_bible_artist": "Locks face and model references from source pages.",
                "keyframe_artist": "Creates opening and closing frames per approved scene.",
                "inbetween_animator": "Creates transition frames only after keyframes are approved.",
                "qc_judge": "Blocks final cut until coverage and approvals pass.",
            },
            shots=shots,
        )

    def _selected_segment(
        self,
        job: dict[str, Any],
        segment_id: str | None,
        require_storyboard_approval: bool,
    ) -> dict[str, Any] | None:
        segments = job.get("segments", [])
        if segment_id:
            segment = self._require_segment(job, segment_id)
            if require_storyboard_approval and not self._latest_asset(job, segment_id, "storyboard", statuses={"approved"}):
                return None
            return segment
        for segment in segments:
            if require_storyboard_approval and not self._latest_asset(job, segment["id"], "storyboard", statuses={"approved"}):
                continue
            return segment
        return None

    def _reference_paths_for_transition(self, job: dict[str, Any], segment_id: str, kind: str) -> list[Path]:
        if kind != "transition":
            return []
        refs = []
        for keyframe_kind in ("keyframe_start", "keyframe_end"):
            asset = self._latest_asset(job, segment_id, keyframe_kind, statuses={"approved", "needs_review"})
            if asset and asset.get("path"):
                refs.append(self._run_dir(job["id"]) / asset["path"])
        return refs

    def _source_page_for_kind(
        self,
        job: dict[str, Any],
        segment: dict[str, Any],
        kind: str,
        frame_index: int | None,
    ) -> int:
        pages = list(segment["page_indexes"])
        if kind == "keyframe_end":
            return int(pages[-1])
        if kind == "transition" and frame_index is not None and len(pages) > 1:
            return int(pages[0] if frame_index <= self._transition_count(job) / 2 else pages[-1])
        return int(pages[0])

    def _prompt_for_asset(
        self,
        job: dict[str, Any],
        segment: dict[str, Any],
        kind: str,
        frame_index: int | None,
        user_notes: str | None,
    ) -> str:
        if kind == "keyframe_start":
            base = segment["start_prompt"]
        elif kind == "keyframe_end":
            base = segment["end_prompt"]
        else:
            total = self._transition_count(job)
            base = (
                f"In-between frame {frame_index}/{total} between the approved opening and closing "
                f"keyframes for {segment['title']}. Preserve the same face model, costume, manga "
                "line style, and story beat while adding smooth anime motion continuity."
            )
        note = f" User regeneration note: {user_notes}" if user_notes else ""
        return (
            f"{base} No speech bubbles, no captions, no readable text, no subtitles inside the frame. "
            "Use the uploaded page(s), character bible, and approved keyframes as references."
            f"{note}"
        )

    def _segment_prompt(self, pages: list[int], beat: str, label: str) -> str:
        return (
            f"{label} for pages {', '.join(map(str, pages))}. Adapt this manga beat: {beat}. "
            "Preserve exact character identity, face, hair, costume, proportions, line weight, "
            "and black-and-white manga style."
        )

    def _asset_stem(self, segment_id: str, kind: str, frame_index: int | None) -> str:
        if kind == "transition":
            return f"{segment_id}_transition_{int(frame_index or 0):02d}"
        return f"{segment_id}_{kind}"

    def _transition_count(self, job: dict[str, Any]) -> int:
        return self._transition_count_from_quality(str(job["settings"].get("quality", "high")))

    def _transition_count_from_quality(self, quality: str) -> int:
        return {"draft": 4, "high": 8, "ultra": 12}.get(quality.lower(), 8)

    def _sync_segment_status(self, job: dict[str, Any], segment_id: str | None) -> None:
        if not segment_id:
            return
        segment = self._require_segment(job, segment_id)
        assets = [asset for asset in job["assets"] if asset.get("segment_id") == segment_id]
        if assets and all(asset["status"] == "approved" for asset in assets if asset["kind"] != "transition"):
            segment["status"] = "approved"
        elif any(asset["status"] == "rejected" for asset in assets):
            segment["status"] = "needs_review"

    def _require_pages(self, job: dict[str, Any]) -> None:
        if not job.get("pages"):
            raise ValueError("Run ingest before this stage.")

    def _require_storyboard(self, job: dict[str, Any]) -> None:
        if not job.get("segments") or not job.get("coverage_manifest"):
            raise ValueError("Run storyboard before this stage.")

    def _require_character_bible_approved(self, job: dict[str, Any]) -> None:
        if not self._latest_asset(job, None, "character_bible", statuses={"approved"}):
            raise ValueError("Approve the character bible before generating keyframes.")

    def _require_segment(self, job: dict[str, Any], segment_id: str) -> dict[str, Any]:
        for segment in job.get("segments", []):
            if segment["id"] == segment_id:
                return segment
        raise ValueError(f"Unknown segment: {segment_id}")

    def _require_asset(self, job: dict[str, Any], asset_id: str) -> dict[str, Any]:
        for asset in job.get("assets", []):
            if asset["id"] == asset_id:
                return asset
        raise ValueError(f"Unknown asset: {asset_id}")

    def _page_images(self, job: dict[str, Any]) -> list[PageImage]:
        return [self._page_image(job, int(page["index"])) for page in job["pages"]]

    def _page_image(self, job: dict[str, Any], page_index: int) -> PageImage:
        page = next(page for page in job["pages"] if int(page["index"]) == page_index)
        path = self._run_dir(job["id"]) / page["clean_path"]
        return PageImage(index=page_index, path=path, width=int(page["width"]), height=int(page["height"]))

    def _character_reference(self, job: dict[str, Any], page_index: int) -> Path | None:
        page = next((page for page in job["pages"] if int(page["index"]) == page_index), None)
        if not page:
            return None
        return self._run_dir(job["id"]) / page["character_path"]

    def _assets_by_kind(self, job: dict[str, Any], kind: str) -> list[dict[str, Any]]:
        return sorted(
            [asset for asset in job.get("assets", []) if asset["kind"] == kind],
            key=lambda item: int(item.get("version", 1)),
        )

    def _assets_for_segment(self, job: dict[str, Any], segment_id: str, kind: str) -> list[dict[str, Any]]:
        return sorted(
            [
                asset
                for asset in job.get("assets", [])
                if asset.get("segment_id") == segment_id and asset["kind"] == kind
            ],
            key=lambda item: (int(item.get("metadata", {}).get("frame_index", 0)), int(item.get("version", 1))),
        )

    def _latest_asset(
        self,
        job: dict[str, Any],
        segment_id: str | None,
        kind: str,
        statuses: set[str] | None = None,
    ) -> dict[str, Any] | None:
        matches = [
            asset
            for asset in job.get("assets", [])
            if asset.get("segment_id") == segment_id and asset["kind"] == kind
        ]
        if statuses:
            matches = [asset for asset in matches if asset["status"] in statuses]
        if not matches:
            return None
        return sorted(matches, key=lambda item: int(item.get("version", 1)))[-1]

    def _subtitle_source_text(self, job_id: str) -> str | None:
        path = self._run_dir(job_id) / "subtitle_source.txt"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def _set_stage(self, job: dict[str, Any], stage: str, status: str, summary: str) -> None:
        job["stages"][stage] = {
            "id": stage,
            "status": status,
            "summary": summary,
            "updated_at": _now(),
        }
        job["active_stage"] = stage
        job["updated_at"] = _now()

    def _message(self, job: dict[str, Any], message: str) -> None:
        job.setdefault("messages", []).append(message)

    def _hydrate(self, job: dict[str, Any]) -> dict[str, Any]:
        hydrated = json.loads(json.dumps(job))
        for asset in hydrated.get("assets", []):
            if asset.get("path") and not asset.get("url"):
                asset["url"] = f"/api/studio/jobs/{job['id']}/files/{asset['path']}"
        hydrated["approvalSummary"] = self._approval_summary(hydrated)
        hydrated["finalizeReadiness"] = self._finalize_readiness(hydrated) if hydrated.get("segments") else {
            "ready": False,
            "missing": ["storyboard has not been created"],
            "summary": "Storyboard has not been created.",
        }
        return hydrated

    def _approval_summary(self, job: dict[str, Any]) -> dict[str, Any]:
        reviewable = [asset for asset in job.get("assets", []) if asset["kind"] != "final_video"]
        approved = [asset for asset in reviewable if asset["status"] == "approved"]
        rejected = [asset for asset in reviewable if asset["status"] == "rejected"]
        blockers = [
            asset["id"]
            for asset in reviewable
            if asset.get("qc", {}).get("blocker") or asset["status"] in {"failed", "rejected"}
        ]
        return {
            "reviewable": len(reviewable),
            "approved": len(approved),
            "rejected": len(rejected),
            "blockers": blockers,
        }

    def _relative(self, job_id: str, path: Path) -> str:
        return path.resolve().relative_to(self._run_dir(job_id).resolve()).as_posix()

    def _url(self, job_id: str, path: Path | None) -> str | None:
        if path is None:
            return None
        return f"/api/studio/jobs/{job_id}/files/{self._relative(job_id, path)}"

    def _run_dir(self, job_id: str) -> Path:
        return self.output_dir / Path(job_id).name

    def _state_path(self, job_id: str) -> Path:
        return self._run_dir(job_id) / "production_state.json"

    def _load(self, job_id: str) -> dict[str, Any]:
        path = self._state_path(job_id)
        if not path.exists():
            raise FileNotFoundError(job_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def _save(self, job: dict[str, Any]) -> None:
        path = self._state_path(job["id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.now(UTC).isoformat()


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
