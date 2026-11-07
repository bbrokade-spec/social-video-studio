# Social Video Studio

A self-hostable orchestration backend for FINOMICS video production.

## What is in this repository

- FastAPI backend with health and provider metadata endpoints.
- Z-Image-Turbo adapter using Gradio's asynchronous event-ID/SSE flow.
- Wan 2.2 adapter using the Space's documented `POST /run/generate_video` JSON endpoint and FileData response.
- End-to-end image-to-video pipeline endpoint.
- Server-side Hugging Face token configuration.
- API-key protection for generation routes, disabled by default until an API key is configured.
- CI checks for syntax and basic API/security behavior.

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
- `GET /api/v1/images/{event_id}`: wait for the Z-Image SSE completion and return FileData outputs.
- `POST /api/v1/videos`: send an existing public image URL to Wan 2.2.
- `POST /api/v1/pipelines/image-to-video`: generate an image, wait for its result, pass its URL to Wan 2.2 and return both outputs.

The pipeline endpoint is synchronous and may run for several minutes. Use a host with an adequate request timeout. A durable background worker/queue is a later hardening step.

FastAPI serves the machine-readable schema at `/openapi.json` and interactive docs at `/docs`.

## Provider contract

The provider endpoint paths and payload structures were transcribed from the live OpenAPI specifications supplied by the project owner. See [docs/API-CONTRACT.md](docs/API-CONTRACT.md). Revalidate them if either Space is updated.

## Deployment

A `Dockerfile` and Render Blueprint file are included. A hosting service must provide:
- HTTPS
- persistent environment secrets
- adequate request timeout for GPU generation
- authentication and rate limits
- optional object storage to persist temporary Gradio files

Render's free web service tier can be used for a test deployment, but free instances sleep when idle, have monthly usage limits and are not recommended for production. Review current limits before deploying.

The service is not deployed by committing this code. Do not expose it publicly until it is deployed behind HTTPS and configured with a strong API key.

## Important limitations

- Hugging Face ZeroGPU capacity and user quota are external and variable.
- Gradio output URLs may be temporary. Production deployment should download and persist generated files promptly.
- Voiceover, subtitles, music, editing and final MP4 assembly remain future modules.
- ChatGPT Go does not currently provide custom MCP write-action connections or creation of new custom GPTs on personal accounts. A hosted API alone does not create a callable ChatGPT tool. See the current [ChatGPT Go plan details](https://help.openai.com/en/articles/11989085-what-is-chatgpt-go), [GPT availability](https://help.openai.com/en/articles/8554407-gpts-in-chatgpt), and [custom MCP availability](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt).

## Security

Keep `HF_TOKEN` and `API_KEY` in hosting secrets, not source control. Use the minimum Hugging Face token scopes needed. Revoke and replace any credential that is exposed.
