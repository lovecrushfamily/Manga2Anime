---
name: context:tests
description: Test runner status, verification commands, and testing gaps for Manga2Anime
keywords: tests, testing, verification, test runner, lint, typecheck, ci, debugging
---

# Manga2Anime - All Tests

Last updated: 2026-06-27

Attach this file after `process/context/all-context.md` when the task involves testing, verification, or test debugging.

## What This Covers

- current automated test availability
- verification commands
- testing gaps worth remembering

## Read This When

Use this file when you need to:

- run tests after implementation
- decide whether a test runner exists
- debug failing tests
- update the test harness after adding a runtime or framework

## Quick Routing

No deeper test docs exist yet. Add routing entries here when the project gains unit, integration, browser, or deployment test documentation.

## Quick Decision Guide

No automated test suite is configured yet. The repository has Python project metadata and optional `pytest` dev dependency, but no committed tests.

For implementation work in the current state:

- Use `python -m py_compile app.py manga2anime/*.py` for a fast backend syntax/import-shape check.
- Use `npm run build` for frontend typecheck/build verification.
- Use a small uploaded chapter with `uvicorn app:app --host 0.0.0.0 --port 8000` and `npm run dev` for manual end-to-end verification.
- Use multipart `curl POST /api/direct` smoke tests for render, subtitle, voiceover, generated-frame, and source-fallback paths.
- Use ffmpeg probe output to confirm MP4 stream shape, audio presence, and duration after voice muxing.
- Use `git status --short` to inspect the worktree before and after edits.

## Commands

| Scope | Runner | Command | Notes |
|---|---|---|---|
| repository status | Git | `git status --short` | confirms changed files |
| syntax check | Python | `python -m py_compile app.py manga2anime/*.py` | no external API key required |
| frontend build | Vite/TypeScript | `npm run build` | verifies React app and production bundle |
| backend API | Uvicorn | `uvicorn app:app --reload --host 0.0.0.0 --port 8000` | serves `/api/direct` and `/api/video/{filename}` |
| frontend dev | Vite | `npm run dev` | serves the React app on port 5173 |
| video encoder | ffmpeg | `ffmpeg -version` | verifies system encoder availability |
| subtitle/voice mux | ffmpeg probe | `ffmpeg -hide_banner -i outputs/{run_id}/manga2anime_{run_id}.final.mp4` | confirms video/audio streams and duration |
| API render smoke | curl | `curl -s -X POST http://127.0.0.1:8000/api/direct ...` | multipart chapter render smoke; tailor form fields per scenario |
| kit agent parity | shell/diff | compare `.claude/agents/*.md` with `.codex/agents/*.toml` | verifies both agent surfaces match |

No project test command exists yet.

## Current Manual/Smoke Scenarios

| Scenario | Strategy | What it proves |
|---|---|---|
| image + subtitle upload, generated frames off, voiceover off | fully automated smoke | `/api/direct` can return a playable MP4 and Japanese SRT URL |
| image + subtitle upload, voiceover on | fully automated smoke | TTS can produce MP3 and mux into `.final.mp4` when OpenAI TTS succeeds |
| ffmpeg probe on final MP4 | fully automated smoke | final MP4 has H.264 video, AAC audio, and expected duration |
| generated frames on with reference-safe source | fully automated smoke | reference-based image generation path can return a generated frame |
| generated frames on with low-detail source | fully automated smoke | identity-detail guard rejects unsafe generated detail and falls back to source frame |
| browser inspection of studio board and result downloads | agent-probe | React UI exposes studio roles, pipeline state, preview, SRT, MP3, and MP4 downloads |

## Debugging Quick Reference

- If a future task asks for automated tests, report that `pytest` is listed as an optional dev dependency but no tests exist yet.
- If ffmpeg rendering fails, check `ffmpeg -version` before debugging Python code.
- If OpenAI calls fail, verify `OPENAI_API_KEY`, model env vars, and account access before changing app logic.
- If generated frames are disabled or fail, the renderer should still fall back to cleaned page animation, not original pages with dialogue.
- API smoke tests should include multipart image upload and optional subtitle upload when touching dialogue/preprocess code.
- If voice mux behavior changes, verify that audio shorter than video does not shorten the final MP4.
- If frame generation prompts change, verify identity lock still avoids text-only generation and rejects unsafe detail additions.

## Known Gaps

- No test runner exists yet.
- No CI configuration exists yet.
- No committed sample manga fixture exists yet.
- No automated assertion exists yet for dialogue-region removal quality.
- No automated browser test exists for the studio UI.
- No committed integration test exists for `/api/direct`.
- No robust semantic identity-similarity test exists; current guard is conservative and density-based.
