# Hugging Face Gradio API contract notes

These notes are based on screenshots of the live OpenAPI specifications supplied by the project owner. Recheck the live schemas before production deployment because Space code and Gradio versions can change.

## Z-Image-Turbo

Base URL: `https://mcp-tools-z-image-turbo.hf.space`

Observed endpoints:
- `POST /gradio_api/upload` (multipart file upload)
- `POST /gradio_api/call/v2/generate`
- `GET /gradio_api/call/generate/{event_id}` (SSE result stream)

Observed positional generation fields, in order:
1. prompt (string)
2. resolution (string preset)
3. seed (integer)
4. steps (number)
5. shift (number)
6. random_seed (boolean)

The POST response supplies an `event_id`. The GET endpoint returns SSE events. The completion event contains an array of outputs, which can include Gradio FileData.

## Wan 2.2

Base URL: `https://zerogpu-aoti-wan2-2-fp8da-aoti-faster.hf.space`

Observed endpoint:
- `POST /run/generate_video`

The request body uses named JSON properties:
- input_image (public URL or base64 encoded image)
- prompt
- negative_prompt
- duration_seconds
- steps
- guidance_scale
- guidance_scale_2
- seed
- randomize_seed

The 200 response contains an `output` property referencing Gradio FileData. The current adapter treats this endpoint as a direct response rather than an event-ID endpoint, based on the supplied OpenAPI response schema.

## Production requirements

Before public deployment:
- Verify request payloads against the live OpenAPI schemas.
- Test both generation calls through the bridge in a controlled, quota-aware session.
- Confirm temporary Gradio URLs remain downloadable and persist assets promptly.
- Apply HTTPS, API-key authentication, rate limiting and upload/request-size limits.
- Do not expose the Hugging Face token to browsers or clients.
- Keep health checks free of GPU calls.
- Configure deployment secrets in the hosting provider, never in Git.
