import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AudioLines,
  Bot,
  Camera,
  Captions,
  Check,
  ChevronRight,
  Clapperboard,
  Download,
  FileImage,
  Film,
  FolderOpen,
  Gauge,
  Image,
  Layers3,
  LoaderCircle,
  Mic2,
  Play,
  RotateCcw,
  Scissors,
  Settings2,
  ShieldCheck,
  Sparkles,
  Upload,
  Wand2,
  X
} from "lucide-react";
import "./styles.css";

type StageId =
  | "ingest"
  | "page_analysis"
  | "storyboard"
  | "character_bible"
  | "segment_keyframes"
  | "segment_inbetweens"
  | "audio"
  | "final_cut";

type ApprovalStatus = "pending" | "running" | "needs_review" | "approved" | "rejected" | "failed" | "complete";

type Health = {
  ok: boolean;
  openaiConfigured: boolean;
  visionModel: string;
  imageModel: string;
};

type StageState = {
  id: StageId;
  status: ApprovalStatus;
  summary: string;
  updated_at: string;
};

type QCReport = {
  status: "pass" | "warning" | "fail";
  score: number;
  blocker?: boolean;
  checks?: Record<string, boolean>;
  notes?: string[];
};

type StudioAsset = {
  id: string;
  segment_id?: string | null;
  kind: string;
  version: number;
  status: ApprovalStatus;
  source_pages: number[];
  prompt: string;
  path?: string | null;
  url?: string | null;
  generated?: boolean;
  qc?: QCReport;
  notes?: string[];
  metadata?: Record<string, unknown>;
};

type SceneSegment = {
  id: string;
  index: number;
  page_indexes: number[];
  title: string;
  beat: string;
  duration: number;
  camera_motion: string;
  transition: string;
  start_prompt: string;
  end_prompt: string;
  subtitle_ja?: string;
  voice_line_ja?: string;
  status: ApprovalStatus;
};

type CoverageManifest = {
  total_pages: number;
  covered_pages: number[];
  page_to_segments: Record<string, string[]>;
  omitted_pages: Array<Record<string, unknown>>;
  coverage_ratio: number;
  complete: boolean;
};

type StudioJob = {
  id: string;
  status: ApprovalStatus;
  active_stage: StageId;
  created_at: string;
  updated_at: string;
  settings: Record<string, unknown>;
  stages: Record<StageId, StageState>;
  uploads: Array<Record<string, unknown>>;
  pages: Array<Record<string, unknown>>;
  page_analysis: Array<Record<string, unknown>>;
  coverage_manifest?: CoverageManifest | null;
  segments: SceneSegment[];
  assets: StudioAsset[];
  final_outputs?: {
    videoUrl?: string;
    subtitleUrl?: string;
    voiceoverUrl?: string | null;
    hasAudio?: boolean;
  };
  approvalSummary?: {
    reviewable: number;
    approved: number;
    rejected: number;
    blockers: string[];
  };
  finalizeReadiness?: {
    ready: boolean;
    missing: string[];
    summary: string;
  };
  messages?: string[];
};

type GuidanceAction =
  | { kind: "none" }
  | { kind: "create_job" }
  | { kind: "run_stage"; stage: StageId; segmentId?: string }
  | { kind: "approve_asset"; assetId: string }
  | { kind: "focus_asset"; assetId: string }
  | { kind: "finalize" };

type FlowStep = {
  label: string;
  state: "done" | "current" | "waiting";
};

type Guidance = {
  title: string;
  detail: string;
  actionLabel: string;
  action: GuidanceAction;
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

const STAGES: Array<{ id: StageId; label: string; icon: React.ElementType }> = [
  { id: "ingest", label: "Ingest", icon: Upload },
  { id: "page_analysis", label: "Pages", icon: FileImage },
  { id: "storyboard", label: "Board", icon: Clapperboard },
  { id: "character_bible", label: "Model", icon: Bot },
  { id: "segment_keyframes", label: "Keys", icon: Image },
  { id: "segment_inbetweens", label: "Motion", icon: Scissors },
  { id: "audio", label: "Audio", icon: Mic2 },
  { id: "final_cut", label: "Final", icon: Film }
];

function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [subtitleFile, setSubtitleFile] = useState<File | null>(null);
  const [stylePrompt, setStylePrompt] = useState(
    "anime hành động kịch tính, nhịp nhanh, camera cận mạnh, line art đen trắng"
  );
  const [duration, setDuration] = useState(20);
  const [maxPages, setMaxPages] = useState(20);
  const [quality, setQuality] = useState<"draft" | "high" | "ultra">("high");
  const [generateFrames, setGenerateFrames] = useState(true);
  const [useVoiceover, setUseVoiceover] = useState(true);
  const [health, setHealth] = useState<Health | null>(null);
  const [job, setJob] = useState<StudioJob | null>(null);
  const [selectedSegmentId, setSelectedSegmentId] = useState<string | null>(null);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busyAction, setBusyAction] = useState<string | null>(null);

  const sortedFiles = useMemo(
    () => [...files].sort((a, b) => displayFileName(a).localeCompare(displayFileName(b))),
    [files]
  );
  const selectedSegment = useMemo(
    () => job?.segments.find((segment) => segment.id === selectedSegmentId) ?? job?.segments[0] ?? null,
    [job, selectedSegmentId]
  );
  const segmentAssets = useMemo(
    () => (selectedSegment && job ? job.assets.filter((asset) => asset.segment_id === selectedSegment.id) : []),
    [job, selectedSegment]
  );
  const globalAssets = useMemo(
    () => (job ? job.assets.filter((asset) => !asset.segment_id) : []),
    [job]
  );
  const visibleAssets = useMemo(
    () => [...globalAssets, ...segmentAssets],
    [globalAssets, segmentAssets]
  );
  const selectedAsset = useMemo(
    () => visibleAssets.find((asset) => asset.id === selectedAssetId) ?? visibleAssets[0] ?? null,
    [selectedAssetId, visibleAssets]
  );
  const coverage = job?.coverage_manifest;
  const canCreateJob = sortedFiles.length > 0 && stylePrompt.trim().length > 0 && !busyAction;
  const finalVideoUrl = job?.final_outputs?.videoUrl;
  const isBusy = Boolean(busyAction);
  const guidance = useMemo(
    () => buildGuidance(job, sortedFiles.length, stylePrompt, selectedSegment, selectedAsset, quality),
    [job, quality, selectedAsset, selectedSegment, sortedFiles.length, stylePrompt]
  );
  const flowSteps = useMemo(() => buildFlowSteps(job, selectedSegment, quality), [job, quality, selectedSegment]);

  useEffect(() => {
    fetch(`${API_BASE}/api/health`)
      .then((response) => response.json())
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    if (!job?.segments.length) return;
    if (!selectedSegmentId || !job.segments.some((segment) => segment.id === selectedSegmentId)) {
      setSelectedSegmentId(job.segments[0].id);
    }
  }, [job, selectedSegmentId]);

  useEffect(() => {
    if (!visibleAssets.length) {
      setSelectedAssetId(null);
      return;
    }
    if (!selectedAssetId || !visibleAssets.some((asset) => asset.id === selectedAssetId)) {
      setSelectedAssetId(visibleAssets[0].id);
    }
  }, [selectedAssetId, visibleAssets]);

  async function createJob() {
    if (!canCreateJob) return;
    await withBusy("create_job", async () => {
      const form = new FormData();
      sortedFiles.forEach((file) => {
        form.append("files", file, displayFileName(file));
      });
      if (subtitleFile) form.append("subtitle_file", subtitleFile);
      form.append("style_prompt", stylePrompt);
      form.append("target_duration", String(duration));
      form.append("max_pages", String(maxPages));
      form.append("quality", quality);
      form.append("use_generated_frames", String(generateFrames));
      form.append("use_voiceover", String(useVoiceover));
      const payload = await postJson<StudioJob>("/api/studio/jobs", form);
      setJob(payload);
      setSelectedSegmentId(null);
      setSelectedAssetId(null);
    });
  }

  async function runStage(stage: StageId, segmentOverride?: string) {
    if (!job) return;
    await withBusy(`stage_${stage}`, async () => {
      const params = new URLSearchParams();
      const segmentId = segmentOverride ?? selectedSegment?.id;
      if ((stage === "segment_keyframes" || stage === "segment_inbetweens") && segmentId) {
        params.set("segment_id", segmentId);
      }
      const suffix = params.toString() ? `?${params.toString()}` : "";
      setJob(await postJson<StudioJob>(`/api/studio/jobs/${job.id}/stages/${stage}/run${suffix}`));
    });
  }

  async function approveAsset(asset: StudioAsset) {
    if (!job) return;
    await withBusy(`approve_${asset.id}`, async () => {
      setJob(await postJson<StudioJob>(`/api/studio/jobs/${job.id}/assets/${asset.id}/approve`, new FormData()));
    });
  }

  async function rejectAsset(asset: StudioAsset) {
    if (!job) return;
    await withBusy(`reject_${asset.id}`, async () => {
      const form = new FormData();
      form.append("notes", "Rejected from studio console.");
      setJob(await postJson<StudioJob>(`/api/studio/jobs/${job.id}/assets/${asset.id}/reject`, form));
    });
  }

  async function regenerateAsset(asset: StudioAsset) {
    if (!job) return;
    await withBusy(`regen_${asset.id}`, async () => {
      const form = new FormData();
      form.append("notes", "Regenerate from human review gate.");
      setJob(await postJson<StudioJob>(`/api/studio/jobs/${job.id}/assets/${asset.id}/regenerate`, form));
    });
  }

  async function approveScene() {
    if (!job || !selectedSegment) return;
    const sceneAssets = job.assets.filter(
      (asset) => asset.segment_id === selectedSegment.id && asset.status === "needs_review" && !asset.qc?.blocker
    );
    if (!sceneAssets.length) return;
    await withBusy(`approve_scene_${selectedSegment.id}`, async () => {
      let nextJob = job;
      for (const asset of sceneAssets) {
        nextJob = await postJson<StudioJob>(`/api/studio/jobs/${nextJob.id}/assets/${asset.id}/approve`, new FormData());
      }
      setJob(nextJob);
    });
  }

  async function approvePassedQc() {
    if (!job) return;
    const reviewable = job.assets.filter((asset) => asset.status === "needs_review" && !asset.qc?.blocker);
    if (!reviewable.length) return;
    await withBusy("approve_passed_qc", async () => {
      let nextJob = job;
      for (const asset of reviewable) {
        nextJob = await postJson<StudioJob>(`/api/studio/jobs/${nextJob.id}/assets/${asset.id}/approve`, new FormData());
      }
      setJob(nextJob);
    });
  }

  async function finalizeJob() {
    if (!job) return;
    await withBusy("finalize", async () => {
      setJob(await postJson<StudioJob>(`/api/studio/jobs/${job.id}/finalize`));
    });
  }

  async function performGuidance() {
    const action = guidance.action;
    if (action.kind === "none") return;
    if (action.kind === "create_job") {
      await createJob();
      return;
    }
    if (action.kind === "run_stage") {
      if (action.segmentId) setSelectedSegmentId(action.segmentId);
      await runStage(action.stage, action.segmentId);
      return;
    }
    if (action.kind === "focus_asset") {
      focusAsset(action.assetId);
      return;
    }
    if (action.kind === "approve_asset") {
      const asset = job?.assets.find((candidate) => candidate.id === action.assetId);
      if (!asset) return;
      focusAsset(asset.id);
      await approveAsset(asset);
      return;
    }
    if (action.kind === "finalize") {
      await finalizeJob();
    }
  }

  function focusAsset(assetId: string) {
    const asset = job?.assets.find((candidate) => candidate.id === assetId);
    if (!asset) return;
    if (asset.segment_id) setSelectedSegmentId(asset.segment_id);
    setSelectedAssetId(asset.id);
  }

  async function withBusy(action: string, task: () => Promise<void>) {
    setBusyAction(action);
    setError("");
    try {
      await task();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Studio action failed.");
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <main className="app-shell">
      <section className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">Studio Production Flow v2</span>
            <h1>Manga2Anime</h1>
          </div>
          <div className="topbar-status">
            <span className="model-status">
              <Sparkles size={17} />
              {health?.openaiConfigured ? "OpenAI ready" : "Fallback mode"}
            </span>
            {job && <span className="job-chip">Job {job.id}</span>}
          </div>
        </header>

        <section className="production-console">
          <aside className="stage-rail" aria-label="Studio stages">
            {STAGES.map((stage) => {
              const Icon = stage.icon;
              const state = job?.stages?.[stage.id];
              const active = job?.active_stage === stage.id;
              const running = busyAction === `stage_${stage.id}`;
              return (
                <button
                  key={stage.id}
                  className={`stage-pill ${active ? "active" : ""} ${state?.status ?? "pending"}`}
                  disabled={!job || isBusy}
                  onClick={() => runStage(stage.id)}
                  title={state?.summary ?? stage.label}
                >
                  {running ? <LoaderCircle className="spin" size={18} /> : <Icon size={18} />}
                  <span>{stage.label}</span>
                </button>
              );
            })}
          </aside>

          <section className="review-pane glass-pane">
            <div className="review-head">
              <div>
                <span className="eyebrow">Review floor</span>
                <h2>{selectedSegment ? selectedSegment.title : "No scene selected"}</h2>
              </div>
              <CoverageMeter coverage={coverage} filesCount={sortedFiles.length} />
            </div>

            <section className="guided-flow">
              <div>
                <span className="eyebrow">Next gate</span>
                <strong>{guidance.title}</strong>
                <p>{guidance.detail}</p>
              </div>
              <button
                className="command-button primary"
                disabled={isBusy || guidance.action.kind === "none"}
                onClick={performGuidance}
              >
                {isBusy ? <LoaderCircle className="spin" size={17} /> : <Play size={17} />}
                {guidance.actionLabel}
              </button>
            </section>

            <div className="flow-strip" aria-label="Production progress">
              {flowSteps.map((step) => (
                <span className={step.state} key={step.label}>
                  {step.state === "done" ? <Check size={13} /> : <ChevronRight size={13} />}
                  {step.label}
                </span>
              ))}
            </div>

            {finalVideoUrl ? (
              <div className="video-shell">
                <video controls src={`${API_BASE}${finalVideoUrl}`}>
                  {job?.final_outputs?.subtitleUrl && (
                    <track
                      kind="subtitles"
                      src={`${API_BASE}${job.final_outputs.subtitleUrl}`}
                      srcLang="ja"
                      label="Japanese"
                      default
                    />
                  )}
                </video>
                <div className="download-row">
                  <a href={`${API_BASE}${finalVideoUrl}`} className="command-button primary" download>
                    <Download size={17} />
                    MP4
                  </a>
                  {job?.final_outputs?.subtitleUrl && (
                    <a href={`${API_BASE}${job.final_outputs.subtitleUrl}`} className="command-button ghost" download>
                      <Captions size={17} />
                      SRT
                    </a>
                  )}
                  {job?.final_outputs?.voiceoverUrl && (
                    <a href={`${API_BASE}${job.final_outputs.voiceoverUrl}`} className="command-button ghost" download>
                      <AudioLines size={17} />
                      MP3
                    </a>
                  )}
                </div>
              </div>
            ) : (
              <div className="empty-cut">
                <Film size={36} />
                <strong>Final cut waits for approved scene assets.</strong>
              </div>
            )}

            <div className="scene-strip" aria-label="Scene timeline">
              {job?.segments.length ? (
                job.segments.map((segment) => (
                  <button
                    key={segment.id}
                    className={`scene-tab ${segment.id === selectedSegment?.id ? "selected" : ""}`}
                    onClick={() => setSelectedSegmentId(segment.id)}
                  >
                    <span>{segment.title}</span>
                    <small>pages {segment.page_indexes.join(", ")}</small>
                  </button>
                ))
              ) : (
                <div className="scene-tab muted">
                  <span>{sortedFiles.length ? `${sortedFiles.length} source file(s)` : "Upload source pages"}</span>
                  <small>storyboard pending</small>
                </div>
              )}
            </div>

            <div className="asset-grid">
              {visibleAssets.length ? (
                visibleAssets.map((asset) => (
                  <button
                    className={`asset-card ${asset.id === selectedAsset?.id ? "selected" : ""}`}
                    key={asset.id}
                    onClick={() => setSelectedAssetId(asset.id)}
                  >
                    <AssetPreview asset={asset} />
                    <span className={`status-badge ${asset.status}`}>{asset.status.replace("_", " ")}</span>
                    <strong>{assetTitle(asset)}</strong>
                    <small>
                      {asset.kind} · v{asset.version}
                      {asset.generated ? " · generated" : " · source"}
                    </small>
                  </button>
                ))
              ) : (
                <div className="asset-empty">
                  <Layers3 size={30} />
                  <span>Run stages to create review assets.</span>
                </div>
              )}
            </div>
          </section>

          <aside className="inspector-pane glass-pane">
            <section className="inspector-section">
              <div className="panel-heading">
                <Upload size={17} />
                <h2>Chapter</h2>
              </div>
              <label className="dropzone">
                <input
                  type="file"
                  multiple
                  accept=".pdf,.png,.jpg,.jpeg,.webp"
                  onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
                />
                <FileImage size={26} />
                <strong>{files.length ? `${files.length} file(s)` : "PDF / ordered JPG pages"}</strong>
              </label>
              <label className="folder-button">
                <input
                  type="file"
                  multiple
                  webkitdirectory=""
                  directory=""
                  accept=".jpg,.jpeg,.png,.webp"
                  onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
                />
                <FolderOpen size={17} />
                Folder
              </label>
              {sortedFiles.length > 0 && (
                <div className="file-list">
                  {sortedFiles.slice(0, 5).map((file) => (
                    <div key={`${displayFileName(file)}-${file.size}`}>
                      <span>{displayFileName(file)}</span>
                      <small>{formatBytes(file.size)}</small>
                    </div>
                  ))}
                  {sortedFiles.length > 5 && <em>+{sortedFiles.length - 5} more</em>}
                </div>
              )}
            </section>

            <section className="inspector-section">
              <div className="panel-heading">
                <Wand2 size={17} />
                <h2>Direction</h2>
              </div>
              <textarea value={stylePrompt} onChange={(event) => setStylePrompt(event.target.value)} />
              <label className="subtitle-picker">
                <input
                  type="file"
                  accept=".srt,.vtt,.txt"
                  onChange={(event) => setSubtitleFile(event.target.files?.[0] ?? null)}
                />
                <Captions size={17} />
                {subtitleFile ? subtitleFile.name : "Subtitle / dialogue file"}
              </label>
            </section>

            <section className="inspector-section compact-controls">
              <div className="panel-heading">
                <Settings2 size={17} />
                <h2>Render</h2>
              </div>
              <div className="control-row">
                <label>Length</label>
                <input min="10" max="45" type="range" value={duration} onChange={(event) => setDuration(Number(event.target.value))} />
                <output>{duration}s</output>
              </div>
              <div className="control-row">
                <label>Pages</label>
                <input min="5" max="30" type="range" value={maxPages} onChange={(event) => setMaxPages(Number(event.target.value))} />
                <output>{maxPages}</output>
              </div>
              <label className="select-row">
                <span>Quality</span>
                <select value={quality} onChange={(event) => setQuality(event.target.value as "draft" | "high" | "ultra")}>
                  <option value="draft">Draft · 4 transitions</option>
                  <option value="high">High · 8 transitions</option>
                  <option value="ultra">Ultra · 12 transitions</option>
                </select>
              </label>
              <label className="toggle-row">
                <input type="checkbox" checked={generateFrames} onChange={(event) => setGenerateFrames(event.target.checked)} />
                <span>OpenAI frame generation</span>
              </label>
              <label className="toggle-row">
                <input type="checkbox" checked={useVoiceover} onChange={(event) => setUseVoiceover(event.target.checked)} />
                <span>Japanese voiceover</span>
              </label>
              <button className="command-button primary wide" disabled={!canCreateJob} onClick={createJob}>
                {busyAction === "create_job" ? <LoaderCircle className="spin" size={18} /> : <Clapperboard size={18} />}
                Create Studio Job
              </button>
              {error && <div className="error-box">{error}</div>}
            </section>

            <section className="inspector-section">
              <div className="panel-heading">
                <ShieldCheck size={17} />
                <h2>Review Gate</h2>
              </div>
              <div className="gate-grid">
                <div>
                  <span>Approved</span>
                  <strong>
                    {job?.approvalSummary?.approved ?? 0}/{job?.approvalSummary?.reviewable ?? 0}
                  </strong>
                </div>
                <div>
                  <span>Blockers</span>
                  <strong>{job?.approvalSummary?.blockers?.length ?? 0}</strong>
                </div>
              </div>
              <button className="command-button ghost wide" disabled={!job || !selectedSegment || isBusy} onClick={approveScene}>
                <Check size={17} />
                Approve Scene
              </button>
              <button className="command-button ghost wide" disabled={!job || isBusy} onClick={approvePassedQc}>
                <ShieldCheck size={17} />
                Approve Passed QC
              </button>
              <button
                className="command-button primary wide"
                disabled={!job?.finalizeReadiness?.ready || isBusy}
                onClick={finalizeJob}
                title={job?.finalizeReadiness?.summary}
              >
                {busyAction === "finalize" ? <LoaderCircle className="spin" size={18} /> : <Play size={18} />}
                Finalize
              </button>
              {job?.finalizeReadiness && !job.finalizeReadiness.ready && (
                <p className="readiness-note">{job.finalizeReadiness.summary}</p>
              )}
            </section>

            {selectedAsset && (
              <section className="asset-inspector">
                <div className="asset-inspector-title">
                  <span className={`status-dot ${selectedAsset.status}`} />
                  <strong>{assetTitle(selectedAsset)}</strong>
                </div>
                <p>{selectedAsset.prompt}</p>
                <div className="qc-list">
                  <span>
                    <Gauge size={15} />
                    QC {Math.round((selectedAsset.qc?.score ?? 0) * 100)}%
                  </span>
                  <span>pages {selectedAsset.source_pages.join(", ") || "system"}</span>
                </div>
                {selectedAsset.qc?.notes?.map((note) => <small key={note}>{note}</small>)}
                <div className="asset-actions">
                  <button className="icon-button approve" disabled={isBusy} onClick={() => approveAsset(selectedAsset)}>
                    <Check size={17} />
                  </button>
                  <button className="icon-button reject" disabled={isBusy} onClick={() => rejectAsset(selectedAsset)}>
                    <X size={17} />
                  </button>
                  <button
                    className="icon-button"
                    disabled={isBusy || !canRegenerate(selectedAsset)}
                    onClick={() => regenerateAsset(selectedAsset)}
                    title={canRegenerate(selectedAsset) ? "Regenerate" : "Regenerate is available for scene image assets"}
                  >
                    <RotateCcw size={17} />
                  </button>
                </div>
              </section>
            )}
          </aside>
        </section>
      </section>
    </main>
  );
}

function CoverageMeter({ coverage, filesCount }: { coverage?: CoverageManifest | null; filesCount: number }) {
  const total = coverage?.total_pages ?? filesCount;
  const covered = coverage?.covered_pages?.length ?? 0;
  const ratio = coverage?.coverage_ratio ?? 0;
  return (
    <div className="coverage-meter">
      <span>{total ? `${covered}/${total} pages covered` : "0/0 pages covered"}</span>
      <div>
        <i style={{ width: `${Math.min(100, Math.round(ratio * 100))}%` }} />
      </div>
    </div>
  );
}

function AssetPreview({ asset }: { asset: StudioAsset }) {
  if (asset.url && asset.url.match(/\.(png|jpg|jpeg|webp)$/i)) {
    return <img src={`${API_BASE}${asset.url}`} alt={assetTitle(asset)} loading="lazy" />;
  }
  const Icon = asset.kind === "voice" ? AudioLines : asset.kind === "subtitle" ? Captions : asset.kind === "final_video" ? Film : ChevronRight;
  return (
    <div className="asset-placeholder">
      <Icon size={28} />
    </div>
  );
}

function buildGuidance(
  job: StudioJob | null,
  fileCount: number,
  stylePrompt: string,
  selectedSegment: SceneSegment | null,
  selectedAsset: StudioAsset | null,
  quality: "draft" | "high" | "ultra"
): Guidance {
  if (!job) {
    if (!fileCount) {
      return {
        title: "Add manga pages",
        detail: "The studio starts after a PDF or ordered image folder is selected.",
        actionLabel: "Waiting for pages",
        action: { kind: "none" }
      };
    }
    if (!stylePrompt.trim()) {
      return {
        title: "Add direction",
        detail: "A style brief is required before creating the job.",
        actionLabel: "Waiting for brief",
        action: { kind: "none" }
      };
    }
    return {
      title: "Create production job",
      detail: `${fileCount} source file(s) ready for intake.`,
      actionLabel: "Create Job",
      action: { kind: "create_job" }
    };
  }

  if (!job.pages.length) {
    return {
      title: "Normalize source pages",
      detail: "Ingest creates clean pages, backgrounds, character cutouts, and dialogue metadata.",
      actionLabel: "Run Ingest",
      action: { kind: "run_stage", stage: "ingest" }
    };
  }

  if (job.page_analysis.length < job.pages.length) {
    return {
      title: "Analyze every page",
      detail: `${job.page_analysis.length}/${job.pages.length} page analysis items are ready.`,
      actionLabel: "Run Page Analysis",
      action: { kind: "run_stage", stage: "page_analysis" }
    };
  }

  if (!job.segments.length || !job.coverage_manifest) {
    return {
      title: "Build storyboard coverage",
      detail: "The director maps all uploaded pages into scene beats before frame generation.",
      actionLabel: "Run Storyboard",
      action: { kind: "run_stage", stage: "storyboard" }
    };
  }

  const storyboardToReview = firstReviewable(job, "storyboard");
  if (storyboardToReview) {
    return selectedAsset?.id === storyboardToReview.id
      ? {
          title: "Approve scene storyboard",
          detail: `${storyboardToReview.segment_id} is waiting for your review.`,
          actionLabel: "Approve Storyboard",
          action: { kind: "approve_asset", assetId: storyboardToReview.id }
        }
      : {
          title: "Review scene storyboard",
          detail: `${storyboardToReview.segment_id} is waiting in the gallery.`,
          actionLabel: "Open Storyboard",
          action: { kind: "focus_asset", assetId: storyboardToReview.id }
        };
  }

  const characterBible = latestAsset(job, null, "character_bible");
  if (!characterBible) {
    return {
      title: "Create character bible",
      detail: "The model sheet locks faces and costumes before generated frames.",
      actionLabel: "Run Model Sheet",
      action: { kind: "run_stage", stage: "character_bible" }
    };
  }
  if (characterBible.status === "needs_review") {
    return selectedAsset?.id === characterBible.id
      ? {
          title: "Approve character bible",
          detail: "Generated frames stay anchored to this approved model sheet.",
          actionLabel: "Approve Model",
          action: { kind: "approve_asset", assetId: characterBible.id }
        }
      : {
          title: "Review character bible",
          detail: "Open the model sheet before keyframes.",
          actionLabel: "Open Model",
          action: { kind: "focus_asset", assetId: characterBible.id }
        };
  }

  const activeSegment = selectedSegment ?? job.segments[0] ?? null;
  if (!activeSegment) {
    return {
      title: "No scene available",
      detail: "Storyboard did not produce any scene segment.",
      actionLabel: "Waiting",
      action: { kind: "none" }
    };
  }

  const keyframeToReview = firstReviewableForSegment(job, activeSegment.id, ["keyframe_start", "keyframe_end"]);
  if (keyframeToReview) {
    return selectedAsset?.id === keyframeToReview.id
      ? {
          title: "Approve keyframe",
          detail: `${activeSegment.title} needs both keyframes approved before motion frames.`,
          actionLabel: "Approve Keyframe",
          action: { kind: "approve_asset", assetId: keyframeToReview.id }
        }
      : {
          title: "Review keyframe",
          detail: `${activeSegment.title} has a keyframe waiting in the gallery.`,
          actionLabel: "Open Keyframe",
          action: { kind: "focus_asset", assetId: keyframeToReview.id }
        };
  }

  const keyframesReady =
    latestAsset(job, activeSegment.id, "keyframe_start")?.status === "approved" &&
    latestAsset(job, activeSegment.id, "keyframe_end")?.status === "approved";
  if (!keyframesReady) {
    return {
      title: "Generate two keyframes",
      detail: `${activeSegment.title} will get an opening and closing frame first.`,
      actionLabel: "Run Keyframes",
      action: { kind: "run_stage", stage: "segment_keyframes", segmentId: activeSegment.id }
    };
  }

  const transitionToReview = firstReviewableForSegment(job, activeSegment.id, ["transition"]);
  if (transitionToReview) {
    return selectedAsset?.id === transitionToReview.id
      ? {
          title: "Approve transition frame",
          detail: `${activeSegment.title} transition strip is waiting frame-by-frame.`,
          actionLabel: "Approve Frame",
          action: { kind: "approve_asset", assetId: transitionToReview.id }
        }
      : {
          title: "Review transition frame",
          detail: `${activeSegment.title} has motion frames waiting in the gallery.`,
          actionLabel: "Open Frame",
          action: { kind: "focus_asset", assetId: transitionToReview.id }
        };
  }

  const transitionTarget = transitionCount(quality);
  const approvedTransitions = assetsFor(job, activeSegment.id, "transition").filter(
    (asset) => asset.status === "approved"
  ).length;
  if (approvedTransitions < transitionTarget) {
    return {
      title: "Generate transition frames",
      detail: `${activeSegment.title} has ${approvedTransitions}/${transitionTarget} approved motion frames.`,
      actionLabel: "Run Transitions",
      action: { kind: "run_stage", stage: "segment_inbetweens", segmentId: activeSegment.id }
    };
  }

  const nextUnfinishedSegment = job.segments.find((segment) => !segmentVisualsApproved(job, segment.id, quality));
  if (nextUnfinishedSegment) {
    return {
      title: "Move to next scene",
      detail: `${nextUnfinishedSegment.title} still needs keyframes or transition approvals.`,
      actionLabel: "Open Scene",
      action: { kind: "focus_asset", assetId: latestAsset(job, nextUnfinishedSegment.id, "storyboard")?.id ?? "" }
    };
  }

  const subtitle = latestAsset(job, null, "subtitle");
  const voice = latestAsset(job, null, "voice");
  const voiceRequired = Boolean(job.settings.use_voiceover);
  if (!subtitle || (voiceRequired && !voice)) {
    return {
      title: "Prepare dialogue assets",
      detail: "Japanese subtitles and optional voice are created after scene motion is approved.",
      actionLabel: "Run Audio",
      action: { kind: "run_stage", stage: "audio" }
    };
  }

  const systemAssetToReview = [subtitle, voice].find((asset): asset is StudioAsset => Boolean(asset && asset.status === "needs_review"));
  if (systemAssetToReview) {
    return selectedAsset?.id === systemAssetToReview.id
      ? {
          title: "Approve dialogue asset",
          detail: `${assetTitle(systemAssetToReview)} is waiting for final cut approval.`,
          actionLabel: "Approve Asset",
          action: { kind: "approve_asset", assetId: systemAssetToReview.id }
        }
      : {
          title: "Review dialogue asset",
          detail: `${assetTitle(systemAssetToReview)} is waiting in the gallery.`,
          actionLabel: "Open Asset",
          action: { kind: "focus_asset", assetId: systemAssetToReview.id }
        };
  }

  if (job.finalizeReadiness?.ready) {
    return {
      title: "Ready for final cut",
      detail: "Coverage and required approvals are complete.",
      actionLabel: "Finalize",
      action: { kind: "finalize" }
    };
  }

  return {
    title: "Resolve final blockers",
    detail: job.finalizeReadiness?.summary ?? "One or more approval gates are still open.",
    actionLabel: "Review Blockers",
    action: { kind: "none" }
  };
}

function buildFlowSteps(
  job: StudioJob | null,
  selectedSegment: SceneSegment | null,
  quality: "draft" | "high" | "ultra"
): FlowStep[] {
  const activeSegment = selectedSegment ?? job?.segments[0] ?? null;
  const steps: FlowStep[] = [
    {
      label: "Ingest",
      state: job?.pages.length ? "done" : "current"
    },
    {
      label: "Coverage",
      state: job?.coverage_manifest?.complete ? "done" : job?.pages.length ? "current" : "waiting"
    },
    {
      label: "Storyboard",
      state: allStoryboardsApproved(job) ? "done" : job?.segments.length ? "current" : "waiting"
    },
    {
      label: "Model",
      state: latestAsset(job, null, "character_bible")?.status === "approved" ? "done" : job?.segments.length ? "current" : "waiting"
    },
    {
      label: "Scene motion",
      state:
        activeSegment && segmentVisualsApproved(job, activeSegment.id, quality)
          ? "done"
          : latestAsset(job, null, "character_bible")?.status === "approved"
            ? "current"
            : "waiting"
    },
    {
      label: "Audio",
      state: latestAsset(job, null, "subtitle")?.status === "approved" ? "done" : allVisualsApproved(job, quality) ? "current" : "waiting"
    },
    {
      label: "Final",
      state: job?.final_outputs?.videoUrl ? "done" : job?.finalizeReadiness?.ready ? "current" : "waiting"
    }
  ];
  return steps;
}

function firstReviewable(job: StudioJob, kind: string) {
  return job.assets.find((asset) => asset.kind === kind && asset.status === "needs_review" && !asset.qc?.blocker) ?? null;
}

function firstReviewableForSegment(job: StudioJob, segmentId: string, kinds: string[]) {
  return (
    job.assets.find(
      (asset) =>
        asset.segment_id === segmentId &&
        kinds.includes(asset.kind) &&
        asset.status === "needs_review" &&
        !asset.qc?.blocker
    ) ?? null
  );
}

function latestAsset(job: StudioJob | null, segmentId: string | null, kind: string) {
  if (!job) return null;
  const matches = job.assets.filter((asset) => (asset.segment_id ?? null) === segmentId && asset.kind === kind);
  if (!matches.length) return null;
  return [...matches].sort((a, b) => a.version - b.version)[matches.length - 1];
}

function assetsFor(job: StudioJob | null, segmentId: string, kind: string) {
  if (!job) return [];
  return job.assets.filter((asset) => asset.segment_id === segmentId && asset.kind === kind);
}

function allStoryboardsApproved(job: StudioJob | null) {
  if (!job?.segments.length) return false;
  return job.segments.every((segment) => latestAsset(job, segment.id, "storyboard")?.status === "approved");
}

function segmentVisualsApproved(job: StudioJob | null, segmentId: string, quality: "draft" | "high" | "ultra") {
  if (!job) return false;
  const start = latestAsset(job, segmentId, "keyframe_start")?.status === "approved";
  const end = latestAsset(job, segmentId, "keyframe_end")?.status === "approved";
  const transitions = assetsFor(job, segmentId, "transition").filter((asset) => asset.status === "approved").length;
  return start && end && transitions >= transitionCount(quality);
}

function allVisualsApproved(job: StudioJob | null, quality: "draft" | "high" | "ultra") {
  if (!job?.segments.length) return false;
  return job.segments.every((segment) => segmentVisualsApproved(job, segment.id, quality));
}

function transitionCount(quality: "draft" | "high" | "ultra") {
  return { draft: 4, high: 8, ultra: 12 }[quality];
}

async function postJson<T>(path: string, body?: BodyInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { method: "POST", body });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail ?? "Request failed.");
  }
  return payload;
}

function assetTitle(asset: StudioAsset) {
  const pretty = asset.kind
    .replace("keyframe_", "key ")
    .replace("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
  if (asset.segment_id) return `${asset.segment_id} · ${pretty}`;
  return pretty;
}

function canRegenerate(asset: StudioAsset) {
  return ["storyboard", "keyframe_start", "keyframe_end", "transition"].includes(asset.kind);
}

function displayFileName(file: File) {
  return (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
}

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
