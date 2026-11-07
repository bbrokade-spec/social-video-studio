from fastapi import Depends, FastAPI, Header, HTTPException

from .config import settings
from .hf_gradio import output_urls, submit_wan, submit_zimage, get_zimage_events
from .schemas import ImageRequest, VideoRequest, JobSubmitResponse, JobResultResponse

app = FastAPI(
    title="Social Video Studio API",
    version="0.1.0",
    description="Secure orchestration API for FINOMICS image and video generation.",
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
    return {"status": "ok", "service": "social-video-studio-api", "generation_called": False}


@app.get("/api/v1/providers")
async def providers():
    return {
        "providers": [
            {"id": "z-image-turbo", "base_url": settings.zimage_base_url, "mode": "text-to-image"},
            {"id": "wan-2.2", "base_url": settings.wan_base_url, "mode": "image-to-video"},
        ],
        "token_configured": bool(settings.hf_token),
        "generation_enabled": bool(settings.api_key) or settings.allow_unauthenticated_generation,
    }


@app.post("/api/v1/images", response_model=JobSubmitResponse, dependencies=[Depends(require_api_key)])
async def create_image(request: ImageRequest):
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
    return JobSubmitResponse(
        provider="z-image-turbo",
        event_id=event_id,
        status="submitted",
        detail="Image generation submitted. Retrieve the result using the event ID.",
    )


@app.get("/api/v1/images/{event_id}", response_model=JobResultResponse, dependencies=[Depends(require_api_key)])
async def read_image(event_id: str):
    events = await get_zimage_events(event_id)
    outputs = output_urls(events)
    status = "completed" if outputs else "pending_or_empty"
    return JobResultResponse(
        provider="z-image-turbo",
        event_id=event_id,
        status=status,
        outputs=outputs,
        raw_events=events,
    )


@app.post("/api/v1/videos", response_model=JobSubmitResponse, dependencies=[Depends(require_api_key)])
async def create_video(request: VideoRequest):
    payload = {
        "data": [
            str(request.input_image),
            request.prompt,
            request.negative_prompt or "",
            request.duration_seconds,
            request.steps,
            request.guidance_scale,
            request.guidance_scale_2,
            request.seed or 0,
            request.randomize_seed,
        ]
    }
    event_id = await submit_wan(payload)
    return JobSubmitResponse(
        provider="wan-2.2",
        event_id=event_id,
        status="submitted",
        detail="Wan request submitted. Result retrieval remains gated pending endpoint contract validation.",
    )


@app.get("/api/v1/videos/{event_id}", response_model=JobResultResponse, dependencies=[Depends(require_api_key)])
async def read_video(event_id: str):
    raise HTTPException(
        501,
        "Wan result retrieval is intentionally disabled until the Space's exact SSE result contract is verified.",
    )
