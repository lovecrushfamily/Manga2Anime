---
name: context:all
description: Root context router and current repository overview for Manga2Anime
keywords: context, repository, architecture, stack, routing, manga2anime, setup
---
# Manga2Anime - All Context

Last updated: 2026-06-27

This file is the root context entrypoint for the repo. Start here before loading deeper context files.

## How This File Works

Every `process/context/` directory has one `all-*.md` entrypoint that acts as a quick router for that domain. This root file is the top-level router. Context groups each have their own `all-{group}.md` entrypoint.

Use the smallest relevant context file:

1. Read `process/context/all-context.md` first.
2. Choose the relevant context group from the routing tables below.
3. Load that group's `all-{group}.md` entrypoint only when the task needs it.
4. Load deeper docs only when the entrypoint points to them.

---

## Project Summary

`Manga2Anime` is a fanmade React + FastAPI studio tool for turning a short manga chapter into a short black-and-white anime-style cut. The user uploads one PDF chapter, ordered page images, or an image folder; enters a style/directing prompt; optionally adds a subtitle/dialogue file; creates a studio job; and runs staged production with human approval gates before finalization.

The current implementation preprocesses each page into cleaned no-dialogue frames, rough background plates, and rough transparent character/ink cutouts. Studio v2 adds file-backed job state in `outputs/{job_id}/production_state.json`, all-page page analysis, a coverage manifest, scene segments, a character bible contact sheet, two keyframes per scene, transition/in-between frames per selected segment, asset approval/reject/regenerate endpoints, Japanese subtitle/voice assets, and a finalization gate that refuses to render until required approvals and coverage pass. The legacy `/api/direct` quick render remains available.

## Changes Since Last Update

- [Product] Added studio-style multi-agent UX: director orchestrator, cameraman, subtitle adapter, Japanese voice director, and animation unit.
- [Product] Added Studio Production Flow v2: `/api/studio/jobs`, staged job execution, approval/reject/regenerate endpoints, coverage manifest, segment keyframes, transition frames, and finalization gating.
- [Product] Added Japanese subtitle export, optional Japanese voiceover, audio download endpoint, and duration-safe final MP4 muxing.
- [Product] Added identity-locked frame generation: reference-only image edit, no text-only generation fallback, and source-frame fallback when generated detail risks changing the character.
- [Product] Replaced the primary React UI with a three-zone liquid-glass production console: stage rail, guided "Next gate" action, review timeline/gallery, and inspector approval controls.
- [Process] Added the first active `direct-anime` SPEC/PLAN artifact set under `process/features/direct-anime/active/manga2anime-studio-flow_27-06-26/`.

## Current Root Entry Points

<!-- GENERATED:routing -->
| File | Read when |
|---|---|
| `process/context/all-context.md` | any substantial planning, research, review, or implementation task |
| `process/context/planning/all-planning.md` | Planning conventions, plan-shape calibration, and plan artifact routing for Manga2Anime |
| `process/context/tests/all-tests.md` | Test runner status, verification commands, and testing gaps for Manga2Anime |

## Current Context Groups

| Group | Entry point | Scope |
|---|---|---|
| `planning/` | `process/context/planning/all-planning.md` | Planning conventions, plan-shape calibration, and plan artifact routing for Manga2Anime |
| `tests/` | `process/context/tests/all-tests.md` | Test runner status, verification commands, and testing gaps for Manga2Anime |
<!-- /GENERATED:routing -->

## Task Routing Table

| If the task involves... | Start with | Then load |
|---|---|---|
| understanding the current repo state | `process/context/all-context.md` | no additional context required unless the task names a domain |
| creating or reviewing implementation plans | `process/context/all-context.md` | `process/context/planning/all-planning.md` |
| tests, verification, or debugging test failures | `process/context/all-context.md` | `process/context/tests/all-tests.md` |
| changing upload, directing, frame generation, or rendering behavior | `process/context/all-context.md` | inspect `app.py` and `manga2anime/` |
| context maintenance | `process/context/all-context.md` | run the kit context validation scripts after changes |

## Repository Structure

Current top-level layout:

```text
Manga2Anime/
  README.md                -- setup, scope, model defaults, and flow docs pointer
  SYSTEM_FLOW.md           -- Mermaid system, studio, sequence, identity, and output diagrams
  LICENSE                  -- MIT license
  pyproject.toml           -- Python package metadata and dependencies
  .env.example             -- OpenAI/model/render configuration template
  app.py                   -- FastAPI backend, studio job endpoints, and legacy Direct Anime endpoint
  package.json             -- React/Vite frontend scripts and dependencies
  src/
    main.tsx               -- React studio production console
    styles.css             -- liquid-glass production UI styling
  manga2anime/
    config.py              -- environment-backed app settings
    loader.py              -- PDF/image chapter ingestion
    dialogue.py            -- subtitle parsing and optional OpenAI vision dialogue extraction
    preprocess.py          -- dialogue removal, rough background plates, character cutouts, motion hints
    director.py            -- OpenAI vision director plan + fallback planner
    frame_generation.py    -- reference-only image generation, identity guard, fallback source frames
    studio.py              -- file-backed studio job state, staged flow, approval gates, coverage manifest, finalization
    subtitles.py           -- Japanese SRT and voice script helpers
    audio.py               -- OpenAI TTS and ffmpeg audio mux helpers
    openai_utils.py        -- OpenAI response/image extraction utilities
    video.py               -- Pillow frame animation and ffmpeg MP4 rendering
  AGENTS.md                -- managed vibecode/Codex protocol file
  CLAUDE.md                -- managed vibecode/Claude protocol file
  .agents/                 -- shared agent/skill symlinks
  .claude/                 -- Claude agents, skills, commands, hooks, settings
  .codex/                  -- Codex agents, skills, hooks, config
  process/
    _seeds/                -- kit seed templates retained for future refreshes
    context/               -- project context entrypoints
    development-protocols/ -- managed development protocol docs
    features/              -- feature-scoped plans, including direct-anime active SPEC/PLAN
    general-plans/         -- cross-cutting plans and backlog
  outputs/                 -- local generated MP4s, git-ignored
```

## Technology Stack

- **Project manifest:** `pyproject.toml`.
- **Language/runtime:** Python 3.11+.
- **Frontend:** React 19 + Vite.
- **Backend API:** FastAPI + Uvicorn.
- **AI provider:** OpenAI Python SDK.
- **Vision/director model:** `OPENAI_VISION_MODEL`, default `gpt-4o`.
- **Image generation model:** `OPENAI_IMAGE_MODEL`, default `gpt-image-1`.
- **TTS model:** `OPENAI_TTS_MODEL`, default `gpt-4o-mini-tts`.
- **TTS voice:** `OPENAI_TTS_VOICE`, default `alloy`.
- **PDF/image ingestion:** `pypdfium2` for PDFs, Pillow for image processing.
- **Preprocessing:** Pillow tile heuristics for dialogue/text removal, rough background plates, character ink cutouts, and motion hints.
- **Video/audio rendering:** Pillow-generated frame sequence encoded by system or bundled `ffmpeg`; optional voice MP3 is muxed into a final MP4.
- **Package managers:** pip / virtualenv for Python, npm for frontend dependencies.
- **Monorepo:** no workspace configuration or `apps/` / `packages/` layout detected.
- **Database:** none detected.
- **Auth:** none detected.
- **Deployment/CI:** no `.github/`, container config, or deployment config detected yet.
- **License:** MIT.

## Key Patterns and Conventions

- **Harness files:** `AGENTS.md`, `CLAUDE.md`, `.claude/`, `.codex/`, `.agents/`, and `process/development-protocols/` are managed by the vibecode kit and should not be adapted with project-specific product notes.
- **Project-specific context:** durable project knowledge belongs under `process/context/`, especially this file and domain-specific `all-*.md` files.
- **Plans:** cross-cutting work belongs in `process/general-plans/{active,completed,backlog}/`; feature-specific work belongs under `process/features/{feature}/{active,completed,backlog}/` once feature folders exist.
- **Fallback mode:** user-facing flows should still produce a demo MP4 without `OPENAI_API_KEY` by animating cleaned pages.
- **Style prompts:** named studios/franchises are translated into broad cinematic traits instead of being copied exactly.
- **Output style:** MVP is black-and-white / line-art only; no color or full-chapter output. Dialogue must not be rendered inside frames; Japanese subtitles and voiceover live outside the frame.
- **Dialogue:** optional `.srt`, `.vtt`, or `.txt` upload is preferred; if absent and `OPENAI_API_KEY` exists, vision OCR tries to extract dialogue as metadata only.
- **Studio roles:** the product maps runtime subsystems to director orchestrator, page analyst, character bible artist, keyframe artist, in-between animator, subtitle editor, Japanese dubbing, and QC judge roles.
- **Studio job API:** primary UI flow uses `/api/studio/jobs`, `/api/studio/jobs/{job_id}/stages/{stage}/run`, `/api/studio/jobs/{job_id}/assets/{asset_id}/approve|reject|regenerate`, `/api/studio/jobs/{job_id}/finalize`, and `/api/studio/jobs/{job_id}/files/{path}`.
- **Human-in-the-loop:** generated/reviewable assets must be approved before finalization. Keyframe generation requires approved storyboard and character bible. Transition generation requires approved keyframes. The UI has a guided "Next gate" CTA so users can progress through the staged flow without memorizing the stage order.
- **Page coverage:** storyboard creates a `CoverageManifest`; every uploaded page must be mapped to at least one scene segment before finalization.
- **Identity lock:** generated frames must preserve character face, hair, outfit, proportions, and original manga line style. If a generated frame is unsafe or too different, the renderer falls back to the cleaned source frame.
- **Plan state:** the active plan is `process/features/direct-anime/active/manga2anime-studio-flow_27-06-26/manga2anime-studio-flow_PLAN_27-06-26.md`. It is `TESTING`, not archived, because formal PVL validate-contract and committed automated E2E coverage are still pending.
- **Naming:** Python modules use snake_case; dataclasses live in `manga2anime/models.py`.

## Environment and Configuration

Config files:

- `.env.example`
- `pyproject.toml`

Environment variables:

- `OPENAI_API_KEY`
- `OPENAI_VISION_MODEL`
- `OPENAI_IMAGE_MODEL`
- `OPENAI_TTS_MODEL`
- `OPENAI_TTS_VOICE`
- `MANGA2ANIME_OUTPUT_DIR`
- `MANGA2ANIME_FPS`
- `MANGA2ANIME_MAX_PAGES`
- `MANGA2ANIME_MAX_SHOTS`

List variable names only. Never document secret values.

## Context Group Lifecycle

Context groups are durable knowledge domains, not feature folders.

Create a group when:

- a topic has 3+ durable docs
- a single doc exceeds roughly 800 lines with separable subtopics
- multiple agents repeatedly need only one slice of a large context file
- the topic maps to a stable operational domain such as tests, infra, database, auth, UI, or workflows

Do not create a group when:

- the content is a temporary report
- the content is a plan or execution artifact
- the topic is feature-specific and belongs in `process/features/...`

## Context Update Protocol

When durable project knowledge changes:

1. Update the smallest relevant context file.
2. Update this file if routing, ownership, naming, stack, or groups changed.
3. Update the owning `all-{group}.md` entrypoint when a group exists.
4. Run the kit context validation scripts when available.

## Source References

- `README.md` -- setup, MVP scope, and run instructions.
- `SYSTEM_FLOW.md` -- Mermaid diagrams for frontend/backend, studio multi-agent runtime, sequence flow, identity lock, and output package.
- `process/features/direct-anime/active/manga2anime-studio-flow_27-06-26/` -- active PRD/SPEC and plan artifacts for the studio flow.
- `pyproject.toml` -- dependencies and Python metadata.
- `app.py`, `manga2anime/`, and `src/` -- current implementation.
- `LICENSE` -- current repository license.
- Installed vibecode kit files under `.claude/`, `.codex/`, `.agents/`, and `process/`.

## Open Questions and Outstanding Work

- Add automated tests for loader, preprocessing/dialogue removal, director fallback, API endpoints, frontend UI, and video rendering.
- Add automated tests for subtitle export, TTS/mux duration, and identity guard fallback.
- Add CI once the dependency/install workflow is stable.
- Broaden real OpenAI image-generation validation with safe sample manga fixtures.
- Improve generated-frame consistency across repeated characters and panels.
- Replace heuristic layer extraction with semantic segmentation/inpainting when ready.
- Add background queueing, richer per-stage progress streaming, and stronger automated browser tests for the React production console.
- Keep the active studio-flow plan in `active/` until PVL/EVL-style validation and user confirmation are complete.

## Scan Metadata

- Generated: 2026-06-27T07:41:09Z
- Repo HEAD: 16f748bdb2b790525f996574cf8750690e81fe38
- Mode: delta update after Manga2Anime studio flow implementation and RIPER artifact sync
- Package manager: pip / virtualenv + npm
