# Social Video Studio: Architecture and Readiness Audit

Audit date: 2026-11-07
Repository: bbrokade-spec/social-video-studio
Audited branch: main
Audit branch: audit/architecture-readiness-2026-11

## Executive assessment

The repository is a useful proof-of-concept orchestration backend, not yet a complete video production application. It currently coordinates two Hugging Face-hosted generation providers: Z-Image-Turbo for text-to-image and Wan 2.2 for image-to-video. It does not yet provide a user-facing studio, durable job processing, asset storage, voiceover, subtitles, music, timeline editing, or final MP4 assembly.

The correct next step is to harden the existing backend and add a local-first production pipeline around it. Do not install Ollama, Pinokio, Stability Matrix, ComfyUI, or large video models as a prerequisite. The owner's ASUS VivoBook X1502VA (Core i5-13420H, 16 GB RAM, Intel UHD integrated graphics, approximately 334 GB free) is suitable for application development, lightweight transcription, media orchestration, FFmpeg rendering, and programmatic motion graphics. It is not a practical target for large diffusion video models such as WAN 2.2 or HunyuanVideo.

## Existing implementation confirmed from source files

- FastAPI application with health and provider metadata endpoints.
- API-key protection for generation routes.
- Z-Image-Turbo adapter using Gradio event IDs and server-sent events.
- Wan 2.2 adapter using a synchronous JSON request and Gradio FileData response.
- Synchronous image-to-video orchestration endpoint.
- Pydantic request/response schemas and environment-based configuration.
- Dockerfile, Render Blueprint, and a GitHub Actions workflow that compiles code and runs pytest.
- Provider API contracts are based on owner-supplied screenshots and must be revalidated against live provider schemas before production.

## Important findings and risks

### P0: Do not expose publicly yet
1. The README and deployment blueprint correctly warn that public deployment requires HTTPS, a strong API key, rate limits, adequate timeouts, and secure secrets.
2. The API key is a single shared secret. There is no user identity, per-user quota, usage accounting, or abuse control.
3. Hugging Face output URLs may be temporary. Generated files need to be downloaded and persisted promptly if the application is to provide reliable projects.
4. The image-to-video pipeline runs synchronously for several minutes. This is fragile behind ordinary web request timeouts and can be interrupted by process restarts.
5. Provider base URLs are configurable. Validate them against an allowlist before attaching the Hugging Face bearer token, so a misconfiguration cannot send credentials to an unintended HTTPS host.
6. Public-image URL validation rejects obvious private IPs and local hostnames, but does not perform DNS resolution and address validation. Strengthen this if the backend ever fetches user-supplied URLs itself. Avoid adding arbitrary URL-fetching endpoints.
7. Provider error and response handling should be reviewed to ensure temporary URLs, provider internals, or sensitive data are not unnecessarily returned to clients or logged.

### P1: Reliability and product completeness
- Add durable background jobs with states (queued, running, succeeded, failed, cancelled), retry policy, timeouts, and idempotency.
- Add persistent asset storage with local storage first and an optional object-storage adapter later.
- Add project records, asset metadata, generation parameters, and reproducible history.
- Add media validation, upload size limits, file type checks, and safe filenames.
- Add FFmpeg-based assembly, audio mixing, captions, aspect-ratio variants, thumbnail generation, and export profiles.
- Add voiceover and transcription as optional pluggable providers, with local CPU-friendly options.
- Add a browser UI for project creation, scene planning, asset review, generation status, timeline assembly, and export.
- Add tests for authentication, malformed provider responses, SSE parsing, timeouts, retry behavior, asset persistence, and media assembly.
- Add CI dependency/security scanning and pinned, reproducible dependencies.

## Recommended target architecture

1. Web UI: React + TypeScript, responsive project dashboard and scene editor.
2. API: retain FastAPI; separate routers, services, provider adapters, and persistence.
3. Job execution: start with a simple local worker and SQLite-backed job queue; introduce Redis/Celery only if measured workload requires it.
4. Database: SQLite for single-user local mode; PostgreSQL only for multi-user hosted deployment.
5. Media pipeline: FFmpeg for deterministic assembly, audio mixing, subtitle burn-in/sidecar, crop/reframe, thumbnails, and MP4 export.
6. Motion graphics: HyperFrames or HTML/CSS-to-video rendering for charts, titles, explainers, and branded scenes.
7. Editing integration: evaluate OpenChatCut as an optional external editor/MCP integration, not as a hard runtime dependency until Windows installation and interoperability are tested.
8. AI providers: keep Z-Image and Wan adapters optional and clearly label external quota, availability, privacy, and latency. Add no paid provider by default.
9. Speech: evaluate Faster-Whisper for local transcription and Piper/Kokoro for local TTS after testing language quality, model licences, CPU speed, and RAM.
10. Local LLM: Ollama remains optional. Use ChatGPT for planning and writing during development; install a local LLM only if offline inference or local agent orchestration becomes a demonstrated requirement.

## Open-source component shortlist and licence review required

- FFmpeg: core media processing; review LGPL/GPL build configuration and codec licensing for distribution.
- HyperFrames: programmatic HTML/CSS-based video rendering; validate current repository health and licence before adoption.
- OpenChatCut: promising timeline editor and agent integration; inspect maturity, release packaging, security model, and AGPL obligations before embedding or distributing.
- Faster-Whisper: transcription; validate model downloads, CPU performance, and model/data terms.
- Piper / Kokoro: local TTS candidates; check the exact repository and voice/model licences independently.
- Docling: valuable for a separate future document-intelligence workbench, not a dependency of the video studio.
- Activepieces / Flowise: optional workflow orchestration candidates; do not add both without a concrete use case.

No third-party repository should be copied into this project until its current licence, dependency tree, maintenance activity, security posture, and Windows compatibility have been inspected.

## Phased implementation plan

### Phase 0: Repository and provider verification
- Inspect every tracked source and test file.
- Run the existing CI workflow and local test suite.
- Revalidate Z-Image and Wan API schemas and quotas.
- Establish a baseline release and backup.
- Produce a dependency and licence inventory.

### Phase 1: Backend hardening
- Add configuration validation and provider-host allowlisting.
- Add structured logging with secret/URL redaction.
- Add robust SSE parsing and provider contract tests.
- Add bounded concurrency and request limits.
- Add durable jobs and local asset persistence.
- Add CI security and dependency checks.

### Phase 2: Production pipeline
- Add FFmpeg preflight and media metadata inspection.
- Add narration, transcription, subtitles, music bed, audio ducking, scene transitions, and export profiles.
- Add programmatic title cards, chart scenes, and motion graphics.
- Add project manifests so an export can be reproduced.

### Phase 3: User interface
- Add project dashboard, scene/shot list, prompt and asset review, job status, preview, and export.
- Add vertical 9:16 and landscape 16:9 presets.
- Keep human approval before expensive generation and final export.

### Phase 4: Optional integrations
- Evaluate OpenChatCut interoperability.
- Add optional local speech models.
- Add optional hosted generation providers only with explicit user approval.
- Consider Ollama only if offline planning/agent tasks justify its RAM use.

### Phase 5: Release readiness
- Windows installation package and one-command setup.
- Automated tests on clean Windows environment.
- Security review, backup/restore, logs, error handling, and user documentation.
- User acceptance test on the VivoBook before any public deployment.

## Explicit hardware decision

Do not install large local video-generation models on the current VivoBook. Do not treat the Intel UHD shared-memory figure as dedicated VRAM. Use the laptop for UI, orchestration, FFmpeg, lightweight graphics, and carefully selected CPU-friendly speech/document models. Any future GPU-backed generation should be an optional external provider or a separate machine, with costs and privacy disclosed before enabling it.

## User intervention gates

The assistant can continue repository research, code review, architecture, documentation, and code changes in a separate GitHub branch. Ask the owner before:
- installing software or model weights on the Windows laptop;
- entering or changing Hugging Face/API credentials;
- creating external hosting resources or deploying publicly;
- enabling paid services or GPU rentals;
- granting additional permissions;
- merging the pull request into main.

## Definition of done

The project is not complete merely when the API returns a provider URL. Completion requires a reproducible local Windows setup, working UI, reliable job tracking, persistent assets, editable project history, narration/subtitles/audio, deterministic MP4 exports in 9:16 and 16:9, tests, security checks, and user acceptance on the owner's laptop. External generative-video availability must be labelled as quota-dependent rather than guaranteed.
