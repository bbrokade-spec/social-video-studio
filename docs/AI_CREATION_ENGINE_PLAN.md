# AI Creation Engine: Implementation Plan

## Product objective

Extend Social Video Studio with an integrated text/script-to-finished-video workflow. Existing editing, media storage, and FFmpeg export remain available and are reused. Uploading user footage must be optional, not required.

## Phase 1: Script and scene planning (manual script)

### User workflow
1. Select an existing project.
2. Open the Create Video workflow.
3. Paste a complete script and choose output format (vertical 9:16 or landscape 16:9).
4. Add scenes manually. Each scene contains scene order, narration text, visual prompt, optional negative prompt, and target duration.
5. Save the script and ordered scene plan to the project.
6. Reopen and edit the plan without losing data.

### Phase 1 scope
- No LLM/API dependency, image or video generation, or voice generation in this milestone.
- Persist scripts and scenes in SQLite.
- Validate project ownership, input lengths, scene counts, duration bounds, and ordering.
- Provide authenticated API endpoints to create, read, update, and delete a project's script plan.
- Add a UI panel for script input and scene editing.
- Keep existing media upload and editing/export workflows intact.

### Proposed data model
- script_plans: id, project_id, title, full_script, output_profile, created_at, updated_at.
- script_scenes: id, plan_id, position, narration_text, visual_prompt, negative_prompt, duration_seconds, generation_status, created_at, updated_at.
A project may have multiple script plans. Each plan has ordered scenes. Scene position must be unique within a plan.

### API design
- POST /api/v1/projects/{project_id}/script-plans
- GET /api/v1/projects/{project_id}/script-plans
- GET /api/v1/script-plans/{plan_id}
- PUT /api/v1/script-plans/{plan_id}
- DELETE /api/v1/script-plans/{plan_id}
Requests use explicit Pydantic schemas, bounded fields, and the existing local API-key authentication.

## Phase 2: AI visual generation
- Generate a still image for each scene with Z-Image.
- Store generated images as project assets, not only temporary provider URLs.
- Track each scene's generation job, provider event ID, status, and sanitized error.
- Display previews and allow prompt edits and regeneration.
- Validate provider API contracts, authentication, rate limits, output URL lifetime, and image dimensions.

## Phase 3: Image-to-video generation
- Submit each approved scene image to WAN 2.2.
- Track jobs individually with retry-safe status and progress.
- Download and persist returned video files locally.
- Confirm URL lifetime, maximum duration, concurrency, queueing, and cost limits before batch orchestration.

## Phase 4: Narration and subtitles
- Add a pluggable speech-generation provider interface.
- Generate per-scene or full-script narration and persist audio assets.
- Generate subtitle cues from script/audio timing and allow correction.
- Do not hardcode a paid provider until provider choice, pricing, and API access are confirmed.

## Phase 5: Automatic assembly
- Assemble generated scene clips in scene order using the existing FFmpeg media engine.
- Mix narration, optional music, and subtitles.
- Reuse current export profiles and export job infrastructure where practical.
- Provide a review step before final export.

## Non-goals for initial release
- Fully automatic scriptwriting or automatic research/fact checking.
- One-click production without review.
- Local execution of large video models on the user's integrated-graphics laptop.

## Engineering principles
- Work only on feature/ai-video-creation-studio until reviewed.
- Preserve compatibility with existing projects and editing/export routes.
- Add safe migrations for existing SQLite databases.
- Add automated tests for storage, schemas, API authorization, CRUD, ordering, and UI behavior.
- Keep provider tokens and local API keys out of logs, browser storage, and source control.
- Never mark a provider workflow complete until a real end-to-end generation test succeeds.