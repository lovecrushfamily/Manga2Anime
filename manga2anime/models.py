from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True)
class PageImage:
    index: int
    path: Path
    width: int
    height: int


@dataclass(frozen=True)
class LayeredPage:
    index: int
    original_page: PageImage
    clean_page: PageImage
    background_path: Path
    character_path: Path
    dialogue_regions: list[tuple[int, int, int, int]]
    foreground_bbox: tuple[int, int, int, int] | None
    motion_hint: str


@dataclass(frozen=True)
class Shot:
    source_page: int
    beat: str
    camera_motion: str
    transition: str
    duration: float
    frame_prompt: str
    animation_notes: str = ""
    subtitle_ja: str = ""
    voice_line_ja: str = ""


@dataclass(frozen=True)
class DirectorPlan:
    chapter_summary: str
    style_directive: str
    shots: list[Shot]
    studio_roles: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "chapter_summary": self.chapter_summary,
            "style_directive": self.style_directive,
            "studio_roles": self.studio_roles,
            "shots": [asdict(shot) for shot in self.shots],
        }


@dataclass(frozen=True)
class RenderFrame:
    path: Path
    source_page: int
    generated: bool


ApprovalStatus = Literal["pending", "running", "needs_review", "approved", "rejected", "failed"]
StudioStage = Literal[
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
class QCReport:
    status: Literal["pass", "warning", "fail"]
    score: float
    checks: dict[str, bool]
    notes: list[str] = field(default_factory=list)

    @property
    def blocker(self) -> bool:
        return self.status == "fail"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "score": self.score,
            "checks": self.checks,
            "notes": self.notes,
            "blocker": self.blocker,
        }


@dataclass(frozen=True)
class PageAsset:
    index: int
    original_path: str
    clean_path: str
    background_path: str
    character_path: str
    width: int
    height: int
    dialogue_regions: list[tuple[int, int, int, int]]
    motion_hint: str
    analysis: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CoverageManifest:
    total_pages: int
    covered_pages: list[int]
    page_to_segments: dict[str, list[str]]
    omitted_pages: list[dict[str, Any]] = field(default_factory=list)

    @property
    def coverage_ratio(self) -> float:
        if self.total_pages <= 0:
            return 0.0
        return len(set(self.covered_pages)) / self.total_pages

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_pages": self.total_pages,
            "covered_pages": self.covered_pages,
            "page_to_segments": self.page_to_segments,
            "omitted_pages": self.omitted_pages,
            "coverage_ratio": self.coverage_ratio,
            "complete": len(set(self.covered_pages)) == self.total_pages and not self.omitted_pages,
        }


@dataclass(frozen=True)
class SceneSegment:
    id: str
    index: int
    page_indexes: list[int]
    title: str
    beat: str
    duration: float
    camera_motion: str
    transition: str
    start_prompt: str
    end_prompt: str
    subtitle_ja: str = ""
    voice_line_ja: str = ""
    status: ApprovalStatus = "pending"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GeneratedAsset:
    id: str
    segment_id: str | None
    kind: str
    version: int
    status: ApprovalStatus
    source_pages: list[int]
    prompt: str
    path: str | None = None
    url: str | None = None
    generated: bool = False
    qc: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    lineage_id: str | None = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProductionJob:
    id: str
    status: ApprovalStatus
    active_stage: StudioStage | str
    created_at: str
    updated_at: str
    settings: dict[str, Any]
    stages: dict[str, dict[str, Any]]
    uploads: list[dict[str, Any]] = field(default_factory=list)
    pages: list[dict[str, Any]] = field(default_factory=list)
    page_analysis: list[dict[str, Any]] = field(default_factory=list)
    coverage_manifest: dict[str, Any] | None = None
    segments: list[dict[str, Any]] = field(default_factory=list)
    assets: list[dict[str, Any]] = field(default_factory=list)
    final_outputs: dict[str, Any] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
