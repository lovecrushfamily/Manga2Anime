# Direct Anime

## Scope

Direct Anime is the core MVP flow that turns a manga chapter into a short black-and-white anime-style highlight. It covers the React upload/folder/subtitle UI, FastAPI upload endpoint, dialogue extraction, dialogue/text removal, rough background/character layer creation, style prompt interpretation, OpenAI-assisted director planning, optional generated action/transition frames, and ffmpeg MP4 output.

This feature does not cover automatic coloring, audio, voice acting, reference-video style learning, or full chapter-length animation.

## Key Source Files

- `src/main.tsx` -- React UI and Direct Anime button flow.
- `app.py` -- FastAPI endpoints for health, directing, and video download.
- `manga2anime/loader.py` -- PDF, ordered image, and folder-upload chapter loading.
- `manga2anime/dialogue.py` -- subtitle parsing and optional OpenAI vision OCR dialogue extraction.
- `manga2anime/preprocess.py` -- dialogue removal, rough background plates, character cutouts, and motion hints.
- `manga2anime/director.py` -- GPT vision director plan and fallback plan.
- `manga2anime/frame_generation.py` -- optional OpenAI-generated action frames and source-page fallback.
- `manga2anime/video.py` -- pan/zoom animation and MP4 rendering through ffmpeg.

## Related Context

- `process/context/all-context.md` -- root project context and current architecture.
- `process/context/tests/all-tests.md` -- verification commands and test gaps.
- `process/context/planning/all-planning.md` -- plan artifact conventions.

## Current Status

Status: in-progress

The MVP vertical slice exists, but the real OpenAI path still needs validation with an API key and sample manga chapter. No automated tests or CI are committed yet.

## Folder Contents

```text
process/features/direct-anime/
  active/       -- in-progress plans for this feature
  completed/    -- archived completed plans
  backlog/      -- deferred/future plans
```

All artifacts colocate inside each task folder. Do not create sibling `reports/` or `references/` directories.
