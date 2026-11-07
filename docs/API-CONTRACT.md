# Hugging Face Gradio API contract notes

These notes are based on the user-provided screenshots of each Space's OpenAPI document. They are not a substitute for retrieving the live OpenAPI JSON during implementation and testing.

## Z-Image-Turbo

Base URL: `https://mcp-tools-z-image-turbo.hf.space`

Observed endpoints:
- `POST /gradio_api/upload`
- `POST /gradio_api/call/v2/generate`
- `GET /gradio_api/call/generate/{event_id}`

Observed generation fields:
- prompt (string, required)
- resolution (string preset, required)
- seed (integer)
- steps (number)
- shift (number)
- random_seed (boolean)

The POST response supplies an event_id. The GET endpoint returns an SSE stream, whose final event contains the JSON result. The output object contains a URL/path or Gradio FileData representation.

**To validate:** Exact positional input ordering and event retrieval path should be rechecked against the live schema before enabling real calls.

## Wan 2.2

Base URL: `https://zerogpu-aoti-wan2-2-fp8da-aoti-faster.hf.space`

Observed endpoint:
- `POST /run/generate_video`

Observed fields:
- input_image (string URL or base64 data)
- prompt
- negative_prompt
- duration_seconds
- steps
- guidance_scale
- guidance_scale_2
- seed
- randomize_seed

Response is described as Gradio FileData metadata with a file URL/path.

**To validate:** Exact response retrieval, any queue/SSE behavior, positional order, and whether authentication headers are required. Do not infer that a returned event ID is a queue session hash.

## Production requirements

Before public deployment:
- Validate both request payloads against the live OpenAPI schemas.
- Confirm temporary file URLs remain downloadable from the service.
- Download generated assets and persist to object storage.
- Apply HTTPS, API-key or OAuth authentication, rate limiting and upload limits.
- Do not expose the Hugging Face token to the browser.
- Keep health checks free of GPU calls.
