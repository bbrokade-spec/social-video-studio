# Social Video Studio

A self-hostable orchestration backend for FINOMICS video production.

## Current scope

This initial foundation provides:
- FastAPI service and health/configuration endpoints.
- Hugging Face Gradio Space adapters for Z-Image-Turbo and Wan 2.2.
- Asynchronous job submission and event-stream/result retrieval.
- Server-side Hugging Face token handling.
- No automatic GPU calls at startup or health-check time.

## Important deployment note

ChatGPT Go cannot be assumed to invoke an arbitrary custom backend directly. This service is designed to expose a documented HTTP API. A ChatGPT-compatible connector or supported tool integration is a separate deployment step.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs.

Set `HF_TOKEN` in `.env` or deployment secrets. Never commit a real token.

## Configuration

See `.env.example`. The default Space URLs are the public Spaces established during the pilot. Generation endpoints can change; verify against each Space's current `/gradio_api/openapi.json`.

## API

- `GET /health`: local service health only. Does not call Hugging Face.
- `GET /api/v1/providers`: configured provider metadata.
- `POST /api/v1/images`: submit Z-Image-Turbo generation.
- `GET /api/v1/images/{event_id}`: wait for and retrieve image output.
- `POST /api/v1/videos`: submit Wan 2.2 generation.
- `GET /api/v1/videos/{event_id}`: wait for and retrieve video output.

The image and video endpoints are documented in OpenAPI at `/docs`.

## Current limitations

- Hugging Face ZeroGPU availability and quota are external dependencies. A successful request is not guaranteed.
- This first iteration is an API adapter, not a hosted production service.
- Asset URLs returned by Gradio may be temporary. Download and persist assets promptly in a production deployment.
- No narration, editing, subtitles, music or MP4 assembly is implemented yet.
- Do not expose this API publicly without HTTPS, authentication, rate limiting and request controls.

## Security

Use a dedicated Hugging Face read token on the server. Never paste tokens into source files, issues, prompts or chat. Rotate a token if it is exposed.
