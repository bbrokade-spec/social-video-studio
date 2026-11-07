# Social Video Studio

A self-hostable orchestration backend for FINOMICS video production.

## What is in this repository

- FastAPI backend with health and provider metadata endpoints.
- Z-Image-Turbo adapter using Gradio's asynchronous event-ID/SSE flow.
- Wan 2.2 adapter using the Space's documented `POST /run/generate_video` JSON endpoint and FileData response.
- Server-side Hugging Face token configuration.
- API-key protection for generation routes, disabled by default until an API key is configured.
- Tests for health and safe default behavior.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `API_KEY` and `HF_TOKEN` in `.env`, then run:

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs.

Never commit a real Hugging Face token or API key.

## API endpoints

All generation endpoints require the `X-API-Key` header. The health and provider endpoints do not.

- `GET /health`: local service health. Does not call Hugging Face.
- `GET /api/v1/providers`: configured provider metadata.
- `POST /api/v1/images`: submit a Z-Image-Turbo generation job. Returns an `event_id`.
- `GET /api/v1/images/{event_id}`: waits for the Z-Image SSE completion and returns the FileData outputs.
- `POST /api/v1/videos`: submits a Wan 2.2 request and returns its FileData output when completed.

FastAPI serves the machine-readable schema at `/openapi.json` and interactive docs at `/docs`.

## Provider contract

The provider endpoint paths and payload structures were transcribed from the live OpenAPI specifications supplied by the project owner. See [docs/API-CONTRACT.md](docs/API-CONTRACT.md). Revalidate them if either Space is updated.

## Deployment

This repository contains a Dockerfile. A hosting service must provide:
- HTTPS
- persistent environment secrets
- adequate request timeout for GPU generation
- request authentication and rate limits
- optional object storage to persist temporary Gradio files

The service is not deployed by committing this code. Do not expose it publicly until it is deployed behind HTTPS and configured with a strong API key.

## Important limitations

- Hugging Face ZeroGPU capacity and user quota are external and variable.
- Gradio output URLs may be temporary. Production deployment should download and persist generated files promptly.
- The first version only connects image and video generation. Voiceover, subtitles, music, editing and final MP4 assembly remain future modules.
- ChatGPT Go's ability to directly invoke this backend is a separate integration constraint. A hosted API alone does not create a callable ChatGPT tool.

## Security

Keep `HF_TOKEN` and `API_KEY` in hosting secrets, not source control. Use the minimum Hugging Face token scopes needed. Revoke and replace any credential that is exposed.
