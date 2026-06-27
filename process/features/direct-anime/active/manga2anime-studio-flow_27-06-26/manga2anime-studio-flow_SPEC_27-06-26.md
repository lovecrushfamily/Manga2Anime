---
name: spec:manga2anime-studio-flow
description: "Product requirements for the Manga2Anime studio-style manga-to-anime flow"
date: 27-06-26
metadata:
  node_type: memory
  type: spec
  feature: direct-anime
---

# Manga2Anime Studio Flow SPEC

## Summary

The user wants a professional studio-style tool that turns a small manga chapter upload into a short finished anime segment. The segment should preserve the manga content, use every uploaded page unless the user approves omission, remove dialogue text from frames, keep character identity stable, add scene-by-scene motion, optionally include Japanese subtitles and voiceover outside the artwork, and present each generation step through a simple polished glass-style interface with human approval gates.

## User Stories / Jobs To Be Done

- As a creator, I want to upload one manga chapter as a PDF or an ordered image folder, so that I can quickly create a short anime highlight without manually preparing every page.
- As a creator, I want the system to separate dialogue from the artwork, so that the final anime frames do not contain speech bubbles or visible text.
- As a creator, I want the system to understand the manga's story beats and motion, so that the output is a coherent short anime segment rather than disconnected still images.
- As a creator, I want a studio-like multi-agent flow with director, camera, subtitle, voice, and animation roles, so that the process feels professional and easier to reason about.
- As a creator, I want optional Japanese subtitles and Japanese voiceover, so that the output feels closer to an anime cut while keeping dialogue outside the frame.
- As a creator, I want generated frames to preserve the original character face and style, so that camera/composition can change but the character does not become someone else.
- As a creator, I want every uploaded page to be represented in the storyboard, so that a 16-page upload does not silently become a one-frame or one-page result.
- As a creator, I want to approve or regenerate scene storyboards, keyframes, transition frames, and voice/subtitle assets, so that the final cut is assembled only from accepted material.
- As a creator, I want a simple Apple-like liquid glass interface, so that the tool feels clean, modern, and focused while still showing useful studio progress.

## What The User Wants (Behavioral Outcomes)

- The user can choose a PDF, several page images, or a folder of manga images.
- The user can add an optional subtitle or dialogue file.
- The user can set style direction, target duration, page limit, quality mode, generated-frame mode, and Japanese voiceover mode.
- The system creates a file-backed studio job with stage status, reviewable assets, approval state, and production outputs.
- The system produces a playable MP4 anime segment only after required coverage and asset approvals pass.
- The system removes in-frame dialogue text and keeps dialogue as subtitles or voice outside the artwork.
- The system generates all-page analysis, a page coverage manifest, scene segments, two keyframes per scene, transition/in-between frames, camera motion, transitions, and short Japanese lines.
- The UI visualizes the production as a studio console: stage rail, scene timeline/review gallery, inspector, approval controls, and finalization readiness.
- If generated frames cannot preserve character identity, the system keeps the cleaned source frame instead of inventing a different face.
- The user can download the MP4, Japanese subtitle file, and Japanese voice file when available.
- The system still produces a demo-style MP4 when advanced AI generation is unavailable.

## Flow / State Diagram

```text
[create studio job]
        |
        v
[ingest all uploaded pages + clean text]
        |
        v
[analyze every page + build coverage manifest]
        |
        v
[storyboard scenes from 1-2 pages each]
        |
        v
{human approves storyboard + character bible?}
        |
        v
[generate 2 keyframes for selected scene]
        |
        v
{human approves both keyframes?}
        |
        v
[generate transition frames for selected scene]
        |
        v
{human approves transition strip?}
        |
        v
[repeat per scene]
        |
        v
[Japanese SRT / optional voice asset]
        |
        v
{coverage complete + all required assets approved?}
        |
        v
[render final MP4 from approved assets only]
```

## Acceptance Criteria (Testable Outcomes)

- AC1: The user can submit one PDF, multiple page images, or an image folder, create a studio job, run stages, approve required assets, and receive a playable short MP4.
  proven by: studio-job-finalize-smoke
  strategy: Fully-Automated

- AC2: The final anime frames do not show dialogue text, captions, subtitles, or speech bubbles inside the artwork.
  proven by: dialogue-removal-layer-output-probe
  strategy: Hybrid

- AC3: The storyboard coverage manifest maps every uploaded page to at least one scene unless the user approves omission.
  proven by: coverage-manifest-all-pages-smoke
  strategy: Fully-Automated

- AC4: The UI exposes a studio-style production console with stage rail, scene review gallery, inspector, approval buttons, regenerate, and finalize gating.
  proven by: studio-console-browser-visual-probe
  strategy: Agent-Probe

- AC5: The system can produce Japanese subtitle timing outside the anime frame.
  proven by: japanese-srt-generation-smoke
  strategy: Fully-Automated

- AC6: When voiceover is enabled and speech generation succeeds, the returned MP4 has an audio stream and keeps the intended video duration.
  proven by: voiceover-mux-ffmpeg-probe
  strategy: Fully-Automated

- AC7: Generated keyframes and transition frames use manga page references, character bible/cutout references, and approved keyframes where relevant; they do not rely on text-only generation.
  proven by: reference-backed-frame-generation-smoke
  strategy: Fully-Automated

- AC8: If a generated frame adds too much new character detail or cannot safely preserve identity, the asset falls back to the cleaned source frame and remains reviewable.
  proven by: identity-detail-guard-reviewable-fallback-smoke
  strategy: Fully-Automated

- AC9: When an API key is absent or generation fails, the staged flow still creates reviewable source-frame keyframes/transitions and can finalize after approvals.
  proven by: fallback-source-frame-studio-smoke
  strategy: Fully-Automated

- AC11: Finalization is blocked until coverage, character bible, scene storyboard, keyframes, transition frames, and subtitle assets are approved.
  proven by: no-finalize-before-approval-smoke
  strategy: Fully-Automated

- AC10: The UI remains usable and readable on desktop and mobile-sized screens.
  proven by: responsive-ui-browser-probe
  strategy: Agent-Probe

## Out Of Scope

- Full episode or full chapter-length animation.
- Automatic coloring.
- Background music, foley, and multi-character cast recording.
- Production-grade semantic character segmentation and background inpainting.
- Training from anime video references.
- Exact imitation of a named studio, franchise, or living artist style.
- Rights management for third-party manga uploads.

## Constraints

- The frontend must use React/Vite or Next.js App Router, not Streamlit.
- The UI should feel simple, rounded, Apple-like, glassmorphism/liquid glass.
- Dialogue must not appear inside the final anime frame.
- Character face, hair, outfit, proportions, and manga line style must be preserved when generating frames.
- Camera angle and composition may change only when the character remains recognizably the same.
- Japanese dialogue/subtitles are allowed outside the artwork.
- Secrets must stay in environment configuration and must not be printed or documented.
- The workflow should remain useful without advanced generation by falling back to cleaned source frames as reviewable assets.
- Generation must run per segment: two keyframes first, human approval, then transition frames.
- Finalization must not run while required assets are unapproved or coverage is incomplete.
- Current test infrastructure is limited; manual and agent-probe verification remains necessary until a real automated test suite is added.

## Open Questions

None for this PRD. Deferred expansion ideas are listed as out of scope or test-infrastructure follow-up items.

## Background / Research Findings

- The repo currently contains a React/Vite frontend, a FastAPI backend, and a Python package for loading, preprocessing, planning, frame generation, subtitles, audio, and video rendering.
- The active feature folder is `direct-anime`; no previous active plan artifact existed before this sync.
- Current verification context lists no formal automated test suite. Available gates are frontend build, Python compile, API smoke tests, browser/agent probes, and ffmpeg stream inspection.
- Implemented behavior already includes upload intake, subtitle parsing, dialogue removal, rough background and character layer extraction, director planning, optional generated frames, Japanese subtitle export, optional Japanese voiceover, duration-safe audio muxing, studio UI, and identity-lock fallback behavior.
- A generated-frame smoke using a very simple source proved why identity guard is required: when the source lacks enough facial detail, generation can invent a face. The guard now rejects that case and uses the cleaned source frame instead.
