from fastapi import Depends, FastAPI, Header, HTTPException

from .config import settings
from .hf_gradio import generate_wan, get_zimage_events, submit_zimage, _find_filedata
from .schemas import (
    ImageRequest,
    VideoRequest,
    ImageJobSubmitResponse,
    ImageJobResultResponse,
    VideoResultResponse,
)

app = FastAPI(
    title="Social Video Studio API",
    version="0.2.0",
    description="Orchestration API for FINOMICS image and video generation.",
)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if settings.allow_unauthenticated_generation:
        return
    if not settings.api_key:
        raise HTTPException(503, "Set API_KEY before enabling generation endpoints.")
    if x_api_key != settings.api_key:
        raise HTTPException(401, "Missing or invalid API key.")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "social-video-studio-api",
        "generation_called": False,
    }


@app.get("/api/v1/providers")
async def providers():
    return {
        "providers": [
            {
                "id": "z-image-turbo",
                "base_url": settings.zimage_base_url,
                "mode": "text-to-image",
                "generation": "asynchronous event_id + SSE",
            },
            {
                "id": "wan-2.2",
                "base_url": settings.wan_base_url,
                "mode": "image-to-video",
                "generation": "synchronous /run/generate_video",
            },
        ],
        "token_configured": bool(settings.hf_token),
        "generation_enabled": bool(settings.api_key) or settings.allow_unauthenticated_generation,
    }


@app.post(
    "/api/v1/images",
    response_model=ImageJobSubmitResponse,
    dependencies=[Depends(require_api_key)],
)
async def create_image(request: ImageRequest):
    # Positional list follows the Z-Image Space schema shown in its OpenAPI document:
    # prompt, resolution, seed, steps, shift, random_seed.
    payload = {
        "data": [
            request.prompt,
            request.resolution,
            request.seed,
            request.steps,
            request.shift,
            request.random_seed,
        ]
    }
    event_id = await submit_zimage(payload)
    return ImageJobSubmitResponse(
        event_id=event_id,
        status="submitted",
        detail="Image generation submitted. Retrieve it using the event_id.",
    )


@app.get(
    "/api/v1/images/{event_id}",
    response_model=ImageJobResultResponse,
    dependencies=[Depends(require_api_key)],
)
async def read_image(event_id: str):
    events = await get_zimage_events(event_id)
    error_events = [event for event in events if event["event"] == "error"]
    if error_events:
        raise HTTPException(502, "Z-Image reported a generation error")
    complete_events = [event for event in events if event["event"] == "complete"]
    outputs = []
    for event in complete_events:
        outputs.extend(_find_filedata(event.get("data")))
    status = "completed" if complete_events else "pending"
    return ImageJobResultResponse(
        event_id=event_id,
        status=status,
        outputs=outputs,
        events=events,
    )


@app.post(
    "/api/v1/videos",
    response_model=VideoResultResponse,
    dependencies=[Depends(require_api_key)],
)
async def create_video(request: VideoRequest):
    # Wan Space OpenAPI shows named JSON fields and a direct FileData result.
    payload = {
        "input_image": _validate_image_url(str(request.input_image)),
        "prompt": request.prompt,
        "negative_prompt": request.negative_prompt or "",
        "duration_seconds": request.duration_seconds,
        "steps": request.steps,
        "guidance_scale": request.guidance_scale,
        "guidance_scale_2": request.guidance_scale_2,
        "seed": request.seed,
        "randomize_seed": request.randomize_seed,
    }
    result = await generate_wan(payload)
    return VideoResultResponse(output=result["output"], raw_response=result["raw_response"])


def _validate_image_url(url: str) -> str:
    from .hf_gradio import _validate_public_image_url

    return _validate_public_image_url(url)
