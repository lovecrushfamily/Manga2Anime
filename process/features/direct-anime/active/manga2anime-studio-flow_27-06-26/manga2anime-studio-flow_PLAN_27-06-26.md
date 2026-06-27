---
name: plan:manga2anime-studio-flow
description: "Complex plan and handoff for the Manga2Anime studio-style direct anime flow"
date: 27-06-26
feature: direct-anime
metadata:
  node_type: memory
  type: plan
---

# Manga2Anime Studio Flow Plan

**Date**: 27-06-26  
**Status**: 🧪 TESTING — implementation is substantially present; formal PVL validate-contract, automated E2E tests, and user confirmation are still pending.  
**Complexity**: Complex standard plan, one execution stream  
**SPEC**: `process/features/direct-anime/active/manga2anime-studio-flow_27-06-26/manga2anime-studio-flow_SPEC_27-06-26.md`  
**Selected Feature**: `direct-anime`

## Overview

Build and harden the Manga2Anime studio flow: a React/Vite production console and FastAPI backend that turn a PDF or image-folder manga chapter into a short black-and-white anime segment with no dialogue text inside frames, all-page coverage, file-backed studio job state, human approval gates, two keyframes per scene, transition frames, Japanese subtitle export, optional Japanese voiceover, duration-safe final MP4 muxing, and identity-locked character preservation.

## Quick Links

- [Context Envelope](#context-envelope)
- [Context and Goals](#context-and-goals)
- [Phase Completion Rules](#phase-completion-rules)
- [Execution Brief](#execution-brief)
- [Architecture Decisions](#architecture-decisions-final)
- [Implementation Checklist](#implementation-checklist)
- [Acceptance Criteria](#acceptance-criteria)
- [Touchpoints](#touchpoints)
- [Public Contracts](#public-contracts)
- [Blast Radius](#blast-radius)
- [Verification Evidence](#verification-evidence)
- [Resume and Execution Handoff](#resume-and-execution-handoff)
- [Validate Contract](#validate-contract)

## Context Envelope

| # | Field | Value |
|---|---|---|
| 1 | `feature` | `direct-anime` |
| 2 | `phase` | `PLAN / UPDATE-PROCESS sync` |
| 3 | `session-goal` | Summarize user PRD, create RIPER plan artifact, run context discovery, and sync durable context with implemented Manga2Anime studio flow. |
| 4 | `branch` | `main` |
| 5 | `worktree` | `/home/lovecrush/Documents/Manga2Anime` |
| 6 | `context-group` | `planning`, `tests`, root project context |
| 7 | `blast-radius-packages` | `app.py`, `manga2anime/*`, `src/*`, `README.md`, `SYSTEM_FLOW.md`, `process/context/*`, `process/features/direct-anime/*` |
| 8 | `active-plan` | `process/features/direct-anime/active/manga2anime-studio-flow_27-06-26/manga2anime-studio-flow_PLAN_27-06-26.md` |
| 9 | `test-runner` | `python -m py_compile | npm run build | curl API smoke | ffmpeg probe` |
| 10 | `validate-contract` | `pending` |

## Context and Goals

### Product Goal

Deliver a short manga-to-anime creation tool that feels like a small production studio. The user uploads source manga, directs the style, and receives a playable anime segment with clean frames, camera motion, Japanese dialogue assets, and output downloads.

### Current Status

| Area | Status | Notes |
|---|---|---|
| React/Vite UI | 🔨 CODE DONE | Three-zone production console is present: stage rail, review gallery/timeline, inspector approval controls. |
| FastAPI studio API | 🔨 CODE DONE | `/api/studio/jobs`, stage run, approve/reject/regenerate, asset file serving, and finalize endpoints are present. |
| Legacy FastAPI `/api/direct` | 🔨 CODE DONE | Multipart quick-render path remains available. |
| Text removal and layers | 🔨 CODE DONE | Heuristic clean/background/character outputs are present. |
| Studio job state | 🔨 CODE DONE | `outputs/{job_id}/production_state.json` tracks stages, pages, segments, assets, approvals, and outputs. |
| Page coverage and storyboard | 🧪 TESTING | All-page analysis, coverage manifest, and 1-2 page scene grouping are present; needs broad real manga testing. |
| Generated frames | 🧪 TESTING | Segment keyframes and transitions use source/character/keyframe references with fallback; needs real OpenAI fixture testing. |
| Japanese subtitle and voiceover | 🧪 TESTING | SRT/TTS/mux smoke passed; needs automated regression tests. |
| Process artifacts | 🧪 TESTING | SPEC/PLAN/context/System Flow updated for Studio Production Flow v2. |

### Non-Goals

- Full chapter-length animation.
- Automatic coloring.
- Background music, foley, or multi-character cast production.
- Production-grade semantic segmentation or background inpainting.
- CI-grade automated visual identity scoring in this plan.

## Phase Completion Rules

A phase is NOT complete until:

1. **Integration Test** - Works with other system pieces.
2. **Manual Test** - User can perform the action.
3. **Data Verification** - Output files and API response state are confirmed.
4. **Error Handling** - Failure cases are graceful.
5. **User Confirmation** - User says "it works".

Status meanings:

- ⏳ PLANNED - Not started.
- 🔨 CODE DONE - Written but not E2E tested.
- 🧪 TESTING - Currently testing.
- ✅ VERIFIED - Tested AND confirmed working.
- 🚧 BLOCKED - Has issues.

After each phase, document:

- [ ] What was tested manually.
- [ ] Output files/API state verified.
- [ ] Errors encountered and fixed.
- [ ] User confirmation received.

## Execution Brief

### Phase 1: Intake and Preprocess Foundation

**What happens:** Users upload PDF/images/folders. Backend normalizes page order, extracts optional dialogue, removes visible speech/text regions, and writes clean/background/character layer artifacts.

**Integration points:** UI file picker, `/api/direct`, loader, dialogue parser, preprocess unit, output folder.

**Test:** Upload one image, one image folder, and one PDF sample; confirm each produces layered pages and a renderable frame set.

**Verify:** API response reports `layeredPageCount`, `dialogueRegionsRemoved`, `dialogueSource`, and `motionHints`.

**Done when:** User can upload a small chapter and see a playable MP4 with no obvious dialogue text in-frame.

### Phase 2: Studio Director and Animation Pipeline

**What happens:** Backend builds a director plan with studio roles, shot beats, camera motion, transitions, Japanese line metadata, and optional generated action frames.

**Integration points:** direction context, director planner, generated-frame unit, source-frame fallback, renderer.

**Test:** Render with generated frames off and on; confirm fallback still returns a playable MP4.

**Verify:** API response reports shot plan, generated/source frame counts, and studio metadata.

**Done when:** Output is a coherent short anime segment rather than disconnected stills.

### Phase 3: Identity Lock and Dialogue-Off-Frame Guarantees

**What happens:** Generated frames use source page and character cutout references; text-only generation is disabled; generated frames are rejected when they add too much new character detail.

**Integration points:** preprocess character cutout, frame generation, identity guard, fallback copy.

**Test:** Use a source with too little face detail and confirm generated candidate is rejected and source frame is used.

**Verify:** `generatedFrameCount` drops to `0` and `sourceFrameCount` is `1` in the guard smoke.

**Done when:** The system prefers preserving identity over producing a pretty but wrong character.

### Phase 4: Japanese Subtitle, Voiceover, and Final MP4

**What happens:** Director Japanese lines become `.srt`; optional TTS produces voice MP3; ffmpeg mux creates `.final.mp4` without shortening video duration.

**Integration points:** subtitles writer, TTS helper, ffmpeg mux, API static endpoints, frontend download links.

**Test:** Run voice-enabled smoke and inspect final MP4 streams.

**Verify:** API response has `hasAudio: true`, `voiceoverSource: openai_tts`, `subtitleUrl`, and `voiceoverUrl`; ffmpeg probe shows H.264 video plus AAC audio at the target duration.

**Done when:** The user can preview/download a final MP4, Japanese SRT, and voice MP3.

### Phase 5: Studio UI and Process Sync

**What happens:** React UI shows the studio crew board and pipeline status; docs and process artifacts match the implementation.

**Integration points:** React app, CSS, README, Mermaid system flow, process context, active plan artifacts.

**Test:** Build frontend, inspect browser UI, and validate plan/context artifacts.

**Verify:** `npm run build`, plan validation, context validation, and visual probe pass.

**Done when:** A future agent can resume from context + plan without rediscovering the whole system.

### Expected Outcome

- Users can render a short anime segment from manga inputs.
- Frames are cleaned of dialogue text.
- Dialogue is available as Japanese SRT and optional voiceover outside the artwork.
- Generated frames are identity-locked and fail closed to source frames.
- The UI communicates a professional studio pipeline.
- Process artifacts describe the product, plan, and verification state truthfully.

## Phased Execution Workflow

This plan uses a phase-by-phase execution model with built-in verification gates.

For each phase:

1. **Pre-Phase Research** - Read existing code patterns and identify blockers. Present findings before writing code when this is a future implementation phase.
2. **Detailed Planning** - Confirm exact files, contracts, and success criteria.
3. **Implementation** - Execute the approved checklist only.
4. **Testing and Verification** - Run the named gates and record output.
5. **User Confirmation** - Present what is functional, what was tested, what the user can test, and what is ready next.

Do not mark a phase ✅ VERIFIED until integration test, manual test, output verification, error handling, and user confirmation are all done.

## Architecture Decisions (Final)

### AD-001: React/Vite Frontend, Not Streamlit

**Decision:** Use React/Vite as the app shell.

**Rationale:** The user explicitly rejected Streamlit and wanted React component structure. The current app has a real frontend with upload controls, progress/status visualization, preview, and downloads.

**Implications:** Frontend verification uses `npm run build` plus browser/agent visual probes until real UI tests are added.

### AD-002: FastAPI Studio Job API

**Decision:** Use file-backed studio jobs as the primary production API while keeping `/api/direct` as a legacy quick-render path.

**Rationale:** The user needs human approval at each generation step. A single render request cannot show generated frames, collect approvals, regenerate individual assets, or guarantee all uploaded pages are represented.

**Implications:** The primary contract is `/api/studio/jobs`, staged execution, asset approval/reject/regenerate, file serving, and finalization readiness. `/api/direct` remains covered as a fallback demo path.

### AD-003: Studio Roles as Product Model

**Decision:** Model the workflow as director orchestrator, page analyst, character bible artist, keyframe artist, in-between animator, subtitle adapter, Japanese voice director, and QC judge.

**Rationale:** The user asked for a professional studio-style multi-agent flow with human-in-the-loop QA/QC. These roles match concrete backend stages and GUI review gates.

**Implications:** The implementation is still one backend process, but the product/UX maps each subsystem to a studio role and stage status.

### AD-004: Dialogue Off-Frame Only

**Decision:** Dialogue text is removed from frames and represented through metadata, SRT, or voiceover.

**Rationale:** The user explicitly requires the anime output not to contain dialogue in the frame.

**Implications:** Image prompts, preprocess, and UI output must never render subtitles or speech bubbles inside generated art.

### AD-005: Identity-Locked Frame Generation

**Decision:** Use source page + character cutout references for image editing; remove text-only image generation fallback; reject over-detailed generated frames.

**Rationale:** The user explicitly requires generated frames to preserve the character's face and style. A pretty generated frame is unacceptable if it changes identity.

**Implications:** Generated frame count may be lower, but identity preservation wins. Broader face-consistency testing remains required.

### AD-006: Duration-Safe Voice Mux

**Decision:** Mux voiceover into final MP4 using measured video duration.

**Rationale:** Voice can be shorter than video; muxing must not shorten the anime segment.

**Implications:** ffmpeg stream/duration probe is a required verification gate.

## High-Level Data Flow

```text
React UI
  -> POST /api/studio/jobs
  -> outputs/{job_id}/production_state.json
  -> run ingest / page_analysis / storyboard / character_bible
  -> approve storyboard + character bible
  -> run selected segment keyframes
  -> approve 2 keyframes
  -> run selected segment transition frames
  -> approve transition strip
  -> run audio assets
  -> approve subtitle/voice
  -> finalization gate
  -> ffmpeg final MP4 from approved assets
  -> UI preview/downloads
```

## Security Posture

- Secrets stay in `.env`/environment variables and are not logged or documented.
- Uploaded files are handled per-run in temp/output directories.
- Download endpoints sanitize `run_id` and filename via `Path(...).name`.
- CORS is limited to local frontend origins for development.
- No auth, multi-user isolation, rate limiting, malware scanning, or production upload hardening exists yet.

## Component Details

### Frontend Studio UI

Responsibilities:

- File and folder upload controls.
- Subtitle file selection.
- Style prompt and render controls.
- Voiceover/generated-frame toggles.
- Studio crew and pipeline status.
- MP4 preview with subtitle track.
- Download links for MP4/SRT/MP3.

### Backend Orchestrator

Responsibilities:

- Validate user input.
- Create run directories.
- Coordinate loader, dialogue, preprocess, director, frame generation, video, subtitles, voice, and mux.
- Return URLs and metadata for the UI.

### Preprocess Unit

Responsibilities:

- Remove likely dialogue/text regions.
- Create cleaned source frames.
- Create rough background and character layer artifacts.
- Infer motion hints.

### Director Unit

Responsibilities:

- Analyze cleaned pages and dialogue context.
- Produce story summary, style directive, studio roles, shots, camera motion, transition, animation notes, and Japanese lines.
- Fall back to deterministic shot plan when OpenAI is unavailable or unusable.

### Frame Artist and Identity QA

Responsibilities:

- Generate optional action frames only from image references.
- Preserve face/hair/outfit/proportions/style.
- Reject frames that add too much new character detail.
- Fall back to cleaned source frames when uncertain.

### Subtitle and Voice Units

Responsibilities:

- Write Japanese SRT.
- Generate Japanese voice MP3 when enabled and available.
- Mux voice into the final MP4 without shortening video.

## Backend Endpoints and Workers

| Endpoint | Purpose | Notes |
|---|---|---|
| `GET /api/health` | Reports app readiness and configured model names. | Does not expose secret values. |
| `POST /api/direct` | Main render orchestration endpoint. | Multipart files, optional subtitle, style and render controls. |
| `GET /api/video/{run_id}/{filename}` | Serves generated MP4 output. | Sanitizes path segments. |
| `GET /api/subtitle/{run_id}/{filename}` | Serves Japanese SRT output. | Created for every run. |
| `GET /api/audio/{run_id}/{filename}` | Serves Japanese voice MP3 output. | Present when TTS succeeds. |

No background worker or queue exists yet; render requests run synchronously.

## API Surface

### `/api/direct` form fields

| Field | Type | Required | Behavior |
|---|---|---|---|
| `files` | file list | yes | One PDF or ordered image pages/folder entries. |
| `subtitle_file` | file | no | `.srt`, `.vtt`, or `.txt` dialogue source. |
| `style_prompt` | text | yes | User direction for cinematic style. |
| `target_duration` | integer | no | Desired output duration in seconds. |
| `max_shots` | integer | no | Shot cap for director plan. |
| `max_pages` | integer | no | Page cap for intake. |
| `use_generated_frames` | boolean | no | Enables reference-based generated frames. |
| `use_voiceover` | boolean | no | Enables Japanese voiceover/TTS. |

### `/api/direct` response fields

| Field | Meaning |
|---|---|
| `runId` | Per-run output folder id. |
| `videoUrl` | MP4 URL, final mux when voice exists. |
| `subtitleUrl` | Japanese SRT URL. |
| `voiceoverUrl` | Japanese voice MP3 URL when generated. |
| `voiceoverSource` | `openai_tts`, `disabled`, or failure/fallback state. |
| `hasAudio` | Whether the returned MP4 includes audio. |
| `japaneseDubbing` | Voice metadata for the UI. |
| `plan` | Director plan and shot list. |
| `generatedFrameCount` | Count of generated action frames used. |
| `sourceFrameCount` | Count of cleaned source fallback frames used. |
| `preprocess` | Layer, dialogue, and motion metadata. |
| `openaiConfigured` | Whether API key exists. |

## Features List

| ID | Priority | Feature | Status |
|---|---|---|---|
| F-001 | Must | Chapter upload from PDF/images/folder | 🔨 CODE DONE |
| F-002 | Must | Style prompt and render controls | 🔨 CODE DONE |
| F-003 | Must | Dialogue removal and off-frame dialogue metadata | 🧪 TESTING |
| F-004 | Must | Directed shot plan and camera animation | 🧪 TESTING |
| F-005 | Must | MP4 output and download | 🧪 TESTING |
| F-006 | Should | Japanese SRT export | 🧪 TESTING |
| F-007 | Should | Japanese voiceover and final audio mux | 🧪 TESTING |
| F-008 | Must | Identity-locked generated frames with source fallback | 🧪 TESTING |
| F-009 | Should | Liquid-glass studio UI | 🔨 CODE DONE |
| F-010 | Should | Mermaid system flow docs | 🔨 CODE DONE |
| F-011 | Must | Formal automated E2E/integration tests | ⏳ PLANNED |

## Acceptance Criteria

- AC1: User can submit manga input and receive a playable short MP4.
- AC2: Final frames do not contain in-frame dialogue text or speech bubbles.
- AC3: Output follows manga content order through directed shot beats and camera motion.
- AC4: UI visualizes director/camera/subtitle/dubbing/animation studio roles.
- AC5: Japanese SRT is produced outside the frame.
- AC6: Voice-enabled runs produce MP4 with audio stream and intended duration.
- AC7: Generated frames are reference-based, never text-only.
- AC8: Identity guard rejects unsafe generated frames and falls back to source.
- AC9: OpenAI-disabled or generation-failed runs still produce usable MP4.
- AC10: UI remains readable and usable across desktop and mobile.

## Implementation Checklist

- [x] Create React/Vite UI for chapter upload, folder upload, subtitle upload, style prompt, render controls, video preview, and downloads.
  - Test: `npm run build`.
- [x] Implement FastAPI `/api/health`, `/api/direct`, video/subtitle/audio download endpoints.
  - Test: API health smoke.
- [x] Implement PDF/image loading and page ordering.
  - Test: image and PDF multipart smoke.
- [x] Implement dialogue/subtitle parsing and optional OCR metadata path.
  - Test: subtitle upload smoke reports `dialogueSource=subtitle_upload`.
- [x] Implement dialogue removal, clean/background/character layers, and motion hints.
  - Test: inspect layer outputs under `outputs/{run_id}/layers`.
- [x] Implement OpenAI/fallback director plan with studio roles, camera motion, Japanese subtitle and voice lines.
  - Test: API response includes `plan.shots`, `studio_roles`, and Japanese line fields.
- [x] Implement optional generated frames from references only.
  - Test: generated-frame smoke reports `generatedFrameCount=1` when safe.
- [x] Implement identity detail guard and source-frame fallback.
  - Test: low-detail source guard smoke reports `generatedFrameCount=0`, `sourceFrameCount=1`.
- [x] Implement MP4 rendering with camera moves.
  - Test: ffmpeg/probe playable MP4 output.
- [x] Implement Japanese SRT export.
  - Test: SRT file has expected timing and Japanese line.
- [x] Implement Japanese voiceover and duration-safe mux.
  - Test: ffmpeg probe shows video stream, AAC audio stream, and target duration.
- [x] Implement glassmorphism studio UI and pipeline board.
  - Test: browser/agent visual probe and `npm run build`.
- [x] Add Mermaid system flow documentation.
  - Test: read `SYSTEM_FLOW.md` and check diagrams render in Mermaid-capable viewer.
- [x] Create SPEC and PLAN artifacts.
  - Test: `validate-plan-artifact.mjs`.
- [ ] Add committed automated backend tests for loader, preprocess, direct endpoint, subtitles, mux, and identity guard.
  - Test: future `pytest` gate.
- [ ] Add committed frontend/browser tests for upload controls, studio board, result actions, and responsive layout.
  - Test: future Playwright/Vitest gate.
- [ ] Add sample fixtures safe for repository use.
  - Test: CI can run direct-api smoke without private manga assets.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Generated art changes character identity | Product fails user requirement | Reference-only generation, strong prompt, identity detail guard, source fallback. |
| Dialogue removal misses text | Output violates no-dialogue-in-frame rule | Keep SRT/voice outside frame; add future visual/text detection tests. |
| OpenAI calls fail or are unavailable | Render could fail | Fallback director/source-frame render; TTS returns failure state without killing video. |
| Long synchronous render | Poor UX for large inputs | Current MVP limits pages/shots; future queue/progress worker. |
| No automated E2E suite | Cannot archive as fully verified | Keep plan active/testing; add test infra backlog items. |
| Secret leakage | Security risk | Only document env var names; never print key values. |

## Integration Notes

- `.env`/environment drives model and output configuration.
- `imageio-ffmpeg` fallback is used when system ffmpeg is unavailable.
- Current output directory is local `outputs/`.
- No database, auth, queue, or production deployment layer exists.
- Browser/server dev ports: frontend `5173`, backend `8000`.

## Touchpoints

| Path | Role |
|---|---|
| `app.py` | FastAPI orchestration and download endpoints. |
| `manga2anime/config.py` | Environment-backed app settings. |
| `manga2anime/loader.py` | PDF/image intake. |
| `manga2anime/dialogue.py` | Subtitle and OCR dialogue metadata. |
| `manga2anime/preprocess.py` | Text removal, layers, motion hints. |
| `manga2anime/director.py` | Director plan, studio roles, identity-preserving prompt constraints. |
| `manga2anime/frame_generation.py` | Reference-only generation and identity guard. |
| `manga2anime/studio.py` | Studio job state machine, stage handlers, approval gates, coverage manifest, finalization. |
| `manga2anime/subtitles.py` | Japanese SRT and voice script. |
| `manga2anime/audio.py` | Japanese TTS and duration-safe mux. |
| `manga2anime/video.py` | Camera animation and MP4 rendering. |
| `manga2anime/openai_utils.py` | Robust OpenAI response parsing. |
| `manga2anime/models.py` | Dataclasses shared across units. |
| `src/main.tsx` | React studio UI and API integration. |
| `src/styles.css` | Liquid-glass styling and responsive layout. |
| `README.md` | Setup, scope, model, and flow docs pointer. |
| `SYSTEM_FLOW.md` | Mermaid system/studio/identity flow diagrams. |
| `.env.example` | Env var template. |
| `process/context/all-context.md` | Durable repo context router. |
| `process/context/tests/all-tests.md` | Verification context. |
| `process/features/direct-anime/active/manga2anime-studio-flow_27-06-26/*` | SPEC/PLAN artifacts. |

## Public Contracts

| Contract | Stability Expectation |
|---|---|
| `/api/health` response | UI depends on `ok`, `openaiConfigured`, `visionModel`, `imageModel`. |
| `/api/studio/jobs` request/response | Primary UI creates file-backed studio jobs from uploads and settings. |
| `/api/studio/jobs/{job_id}` response | UI polls/reads job state, stages, coverage, segments, assets, approvals, readiness. |
| `/api/studio/jobs/{job_id}/stages/{stage}/run` | UI runs staged production; keyframe/transition stages accept `segment_id`. |
| `/api/studio/jobs/{job_id}/assets/{asset_id}/approve|reject|regenerate` | UI human-in-the-loop controls depend on these endpoints. |
| `/api/studio/jobs/{job_id}/finalize` | Final render is blocked until backend readiness passes. |
| `/api/studio/jobs/{job_id}/files/{path}` | UI previews image/video/audio assets from job output folders. |
| `/api/direct` request fields | UI sends current multipart form fields; changes must update UI. |
| `/api/direct` response fields | Legacy quick render expects video/subtitle/voice URLs, counts, plan, preprocess, dubbing metadata. |
| `/api/video/{run_id}/{filename}` | Browser preview and download depend on MP4 media response. |
| `/api/subtitle/{run_id}/{filename}` | Browser subtitle track and SRT download depend on this. |
| `/api/audio/{run_id}/{filename}` | Voice MP3 download depends on this. |
| Output folder structure | Docs and smoke probes inspect per-run artifacts. |
| DirectorPlan/Shot shape | Director, subtitles, renderer, and UI plan display consume these fields. |

## Blast Radius

| Area | Scope | Risk |
|---|---|---|
| Frontend | `src/main.tsx`, `src/styles.css` | UI regressions, responsive layout issues, API field drift. |
| API orchestration | `app.py`, `manga2anime/studio.py` | Multipart handling, job lifecycle, approval gating, endpoint contracts. |
| AI integration | `director.py`, `frame_generation.py`, `audio.py`, `openai_utils.py` | Model/API behavior drift, cost, fallback behavior. |
| Rendering | `video.py`, `audio.py`, ffmpeg | Broken MP4, wrong duration, missing audio stream. |
| Preprocessing | `preprocess.py` | Bad text removal or identity references. |
| Process/docs | `README.md`, `SYSTEM_FLOW.md`, `process/context/*`, plan artifacts | Agent routing and stale context risk. |

Risk class: medium-high, because behavior spans frontend, backend, AI calls, filesystem artifacts, and video/audio rendering.

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| `npm run build` — React/Vite production build and typecheck | Fully-Automated | AC4, AC10 |
| `.venv/bin/python -m py_compile app.py manga2anime/*.py` — backend syntax/import check | Fully-Automated | AC1, AC5, AC6, AC7, AC8, AC9, AC11 |
| service-level staged smoke with synthetic images — create job, ingest, storyboard, approve, keyframes, transitions, audio, finalize | Fully-Automated | AC1, AC3, AC5, AC9, AC11 |
| `curl POST /api/studio/jobs` and `/stages/ingest/run` with image + subtitle — returns job state and ingest artifacts | Fully-Automated | AC1, AC2 |
| `curl POST /api/direct` with image + subtitle, generation off, voice off — legacy quick path returns playable MP4 and SRT URL | Fully-Automated | AC1, AC5, AC9 |
| `curl POST /api/direct` with voice on — returns `hasAudio: true`, `voiceoverSource: openai_tts`, MP4/SRT/MP3 URLs | Fully-Automated | AC5, AC6 |
| ffmpeg probe on final MP4 — confirms H.264 video, AAC audio, and target duration | Fully-Automated | AC6 |
| generated-frame smoke with reference-safe path — confirms generated frame can be used when guard passes | Fully-Automated | AC7 |
| low-detail source identity guard smoke — confirms unsafe generated frame is rejected and source frame is used | Fully-Automated | AC8 |
| inspect generated/layer artifacts for no obvious in-frame dialogue text | Hybrid | AC2 |
| browser/agent visual probe of stage rail, review gallery, inspector, approval buttons, and finalize disabled state | Agent-Probe | AC4, AC10, AC11 |
| user opens `http://localhost:5173`, uploads sample, previews/downloads outputs | Hybrid | AC1, AC4, AC5, AC6, AC10 |

## Test Infra Improvement Notes

- Add `pytest` tests for loader, dialogue parser, preprocess heuristics, subtitle writer, audio mux duration parsing, OpenAI response parsing, and identity detail guard.
- Add FastAPI integration tests using a safe committed fixture and `TestClient`.
- Add Playwright or Vitest coverage for the UI flow, result actions, subtitle track rendering, and responsive breakpoints.
- Add a small fixture set that is licensed/synthetic and includes a clear-face manga sample plus a low-detail identity guard sample.
- Add a CI workflow once the fixture/test gates exist.
- Add visual regression or image-similarity probes for generated frame identity consistency; current density guard is only a conservative first-pass safety gate.

## Validate Contract

(placeholder — vc-validate-agent writes this section before EXECUTE)

Current provisional status: `pending`. This plan must not be archived as fully verified until PVL writes a validate-contract or an explicit skip reason is documented.

## Resume and Execution Handoff

1. **Selected plan file path**: `process/features/direct-anime/active/manga2anime-studio-flow_27-06-26/manga2anime-studio-flow_PLAN_27-06-26.md`
2. **Last completed phase or step**: Code implementation and smoke verification are substantially complete; process sync artifacts are being created in this pass.
3. **Validate-contract status**: Pending. No formal PVL validate-contract has been written yet.
4. **Supporting context files loaded**:
   - `process/context/all-context.md`
   - `process/context/planning/all-planning.md`
   - `process/context/tests/all-tests.md`
   - `process/development-protocols/all-development-protocols.md`
   - `process/development-protocols/vc-system-behavior/01-overview.md`
   - `process/development-protocols/vc-system-behavior/04-research.md`
   - `process/development-protocols/vc-system-behavior/05-spec.md`
   - `process/development-protocols/vc-system-behavior/06-innovate.md`
   - `process/development-protocols/vc-system-behavior/07-plan.md`
   - `process/development-protocols/vc-system-behavior/08-validate.md`
   - `process/development-protocols/vc-system-behavior/09-execute.md`
   - `process/development-protocols/vc-system-behavior/10-update-process.md`
   - `process/development-protocols/plan-lifecycle.md`
   - `process/development-protocols/context-maintenance.md`
5. **Next step for a fresh agent**:
   - Run PVL/VALIDATE on this plan.
   - Add committed automated tests for the existing smoke gates.
   - Keep this plan in `active/` until automated E2E/integration coverage and user confirmation exist.

## Cursor + RIPER-5 Guidance

- Cursor Plan mode: import the Implementation Checklist and continue from unchecked test-infra items.
- RIPER-5: current artifact state is PLAN complete, PVL pending. Next recommended command is to enter VALIDATE/PVL for this selected plan, then only enter EXECUTE if the validate-contract is present and user explicitly says `ENTER EXECUTE MODE`.
- UPDATE PROCESS archival is not recommended yet because the work lacks formal validate-contract and committed automated E2E coverage.

## Change Management

If scope expands to full chapter-length anime, production-grade segmentation, background music, or multi-character casting, create a new phase program rather than extending this single plan.

## Future Work

- Queue/progress worker for long renders.
- Better semantic segmentation and inpainting.
- Real progress events instead of synchronous request blocking.
- Automated subtitle/text visual detection.
- Stronger identity verification using embeddings or face/character consistency probes where legally and technically appropriate.
- Production deployment hardening: auth, rate limits, file scanning, storage lifecycle, and quota/cost controls.
