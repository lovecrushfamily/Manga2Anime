# Manga2Anime Studio Production Flow v2

## 1. Studio Job API Flow

```mermaid
flowchart LR
  User["Studio Operator"] --> UI["React Vite Production Console<br/>src/main.tsx"]

  UI --> Create["POST /api/studio/jobs<br/>uploads + settings"]
  Create --> State["outputs/{job_id}/production_state.json"]

  UI --> RunStage["POST /api/studio/jobs/{job_id}/stages/{stage}/run"]
  RunStage --> Service["StudioService<br/>manga2anime/studio.py"]
  Service --> State

  UI --> Approve["Approve / Reject / Regenerate Asset"]
  Approve --> AssetAPI["/api/studio/jobs/{job_id}/assets/{asset_id}/..."]
  AssetAPI --> State

  UI --> Finalize["POST /api/studio/jobs/{job_id}/finalize"]
  Finalize --> Gate{"Coverage complete<br/>and required assets approved?"}
  Gate -- "no" --> Block["409 with missing approval list"]
  Gate -- "yes" --> Render["FFmpeg final studio cut"]
  Render --> Delivery["MP4 / SRT / MP3 URLs"]
  Delivery --> UI

  UI -. "legacy quick render still available" .-> Direct["POST /api/direct"]
```

## 2. Human-In-The-Loop Stage Machine

```mermaid
flowchart TD
  Start["Create studio job"] --> Ingest["Ingest<br/>normalize every uploaded page<br/>clean text regions<br/>background + character layers"]
  Ingest --> PageAnalysis["Page Analyst<br/>OpenAI vision batch analysis<br/>all pages, 4/page chunks<br/>fallback page summaries"]
  PageAnalysis --> Storyboard["Director / Storyboard<br/>group 1-2 pages per segment<br/>coverage manifest"]

  Storyboard --> Coverage{"Every page mapped?"}
  Coverage -- "no" --> CoverageBlock["Block finalization<br/>requires omission approval in future"]
  Coverage -- "yes" --> StoryReview["Human reviews scene storyboards"]

  StoryReview --> CharacterBible["Character Bible Artist<br/>contact sheet from all page cutouts"]
  CharacterBible --> ModelReview["Human approves character bible"]

  ModelReview --> Keyframes["Keyframe Artist<br/>generate opening + closing frame<br/>for one selected segment"]
  Keyframes --> KeyReview["Human approves 2 keyframes"]
  KeyReview --> Inbetweens["In-between Animator<br/>generate transition frames<br/>Draft 4 / High 8 / Ultra 12"]
  Inbetweens --> MotionReview["Human approves transition strip"]

  MotionReview --> MoreSegments{"More segments?"}
  MoreSegments -- "yes" --> Keyframes
  MoreSegments -- "no" --> Audio["Dialogue / Voice<br/>Japanese SRT + optional TTS MP3"]
  Audio --> AudioReview["Human approves subtitle/voice assets"]
  AudioReview --> FinalGate["Final QC gate"]
  FinalGate --> FinalCut["Final MP4 from approved assets only"]
```

## 3. Multi-Agent Studio Runtime

```mermaid
flowchart TB
  Orchestrator["Director Orchestrator<br/>owns job state, page coverage, approval gates"] --> Intake["Intake Assistant<br/>PDF/images/folder order"]
  Orchestrator --> LayerArtist["Layer Artist<br/>clean page, background plate, character cutout"]
  Orchestrator --> PageAnalyst["Page Analyst<br/>all-page OpenAI/fallback analysis"]
  Orchestrator --> StoryDirector["Story Director<br/>coverage manifest + scene segments"]
  Orchestrator --> CharacterArtist["Character Bible Artist<br/>model sheet from all source pages"]
  Orchestrator --> KeyArtist["Keyframe Artist<br/>2 frames per scene"]
  Orchestrator --> Animator["In-between Animator<br/>transition frames after approval"]
  Orchestrator --> DialogueAgent["Subtitle Adapter<br/>off-frame Japanese SRT"]
  Orchestrator --> VoiceAgent["Japanese Voice Director<br/>OpenAI TTS MP3"]
  Orchestrator --> QC["QC Judge<br/>identity, no text, coverage, approvals"]

  Intake --> PageStore["PageAsset[]"]
  LayerArtist --> PageStore
  PageAnalyst --> Coverage["CoverageManifest"]
  StoryDirector --> Segments["SceneSegment[]"]
  CharacterArtist --> Bible["character_bible.png"]

  Bible --> ModelGate{"Human approved?"}
  Segments --> SceneGate{"Scene approved?"}
  ModelGate --> KeyArtist
  SceneGate --> KeyArtist

  KeyArtist --> KeyAssets["keyframe_start<br/>keyframe_end"]
  KeyAssets --> KeyGate{"Human approved both?"}
  KeyGate --> Animator
  Animator --> TransitionAssets["transition_01..N"]
  TransitionAssets --> MotionGate{"Human approved transitions?"}

  DialogueAgent --> SubtitleAsset["subtitle asset"]
  VoiceAgent --> VoiceAsset["voice asset"]
  SubtitleAsset --> FinalGate{"All required assets approved?"}
  VoiceAsset --> FinalGate
  MotionGate --> FinalGate
  QC --> FinalGate
  FinalGate --> Delivery["Final MP4 package"]
```

## 4. Segment Generation Loop

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant FE as React Console
  participant API as Studio API
  participant ST as StudioService
  participant IMG as OpenAI Image / fallback
  participant OUT as outputs/{job_id}

  U->>FE: Select scene segment
  FE->>API: run segment_keyframes?segment_id=seg_001
  API->>ST: Verify storyboard + character bible approvals
  ST->>IMG: Generate/copy opening keyframe
  ST->>IMG: Generate/copy closing keyframe
  ST->>OUT: Save keyframe assets + QC reports
  API-->>FE: keyframes need review
  U->>FE: Approve both keyframes
  FE->>API: approve keyframe_start / keyframe_end
  FE->>API: run segment_inbetweens?segment_id=seg_001
  ST->>IMG: Generate transition frames using source page + character bible + approved keyframes
  ST->>OUT: Save transition assets + QC reports
  API-->>FE: transition strip need review
  U->>FE: Approve or regenerate individual frames
```

## 5. Output Package

```mermaid
flowchart LR
  Run["outputs/{job_id}"] --> State["production_state.json"]
  Run --> Uploads["uploads/"]
  Run --> Pages["normalized_pages/page_###.png"]
  Run --> Layers["layers/page_###<br/>clean.png<br/>background.png<br/>character.png"]
  Run --> Bible["character_bible/character_bible.png"]
  Run --> Assets["assets/{segment_id}<br/>keyframes + transitions"]
  Run --> SRT["manga2anime_{job_id}.ja.srt"]
  Run --> Voice["manga2anime_{job_id}.voice.mp3"]
  Run --> StudioMP4["manga2anime_{job_id}.studio.mp4"]
  Run --> Final["manga2anime_{job_id}.final.mp4<br/>when voice mux succeeds"]
```
