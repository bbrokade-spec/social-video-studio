from urllib.parse import urljoin
import secrets

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from .config import settings
from .hf_gradio import (
    _find_filedata,
    _validate_public_image_url,
    generate_wan,
    get_zimage_events,
    submit_zimage,
)
from .schemas import (
    ImageJobResultResponse,
    ImageJobSubmitResponse,
    ImageRequest,
    ImageToVideoPipelineRequest,
    ImageToVideoPipelineResponse,
    VideoRequest,
    VideoResultResponse,
)

app = FastAPI(
    title="Social Video Studio API",
    version="0.3.0",
    description="Orchestration API for FINOMICS image and video generation.",
)

api_key_header = APIKeyHeader(
    name="X-API-Key",
    scheme_name="ApiKeyAuth",
    auto_error=False,
)


def require_api_key(x_api_key: str | None = Security(api_key_header)) -> None:
    if settings.allow_unauthenticated_generation:
        return
    if not settings.api_key:
        raise HTTPException(503, "Set API_KEY before enabling generation endpoints.")
    if not secrets.compare_digest(x_api_key or "", settings.api_key):
        raise HTTPException(401, "Missing or invalid API key.")


def _wan_payload(input_image: str, video) -> dict:
    return {
        "input_image": _validate_public_image_url(input_image),
        "prompt": video.prompt,
        "negative_prompt": video.negative_prompt or "",
        "duration_seconds": video.duration_seconds,
        "steps": video.steps,
        "guidance_scale": video.guidance_scale,
        "guidance_scale_2": video.guidance_scale_2,
        "seed": video.seed,
        "randomize_seed": video.randomize_seed,
    }


async def _run_image_to_video(image_request: ImageRequest, video_request):
    # Submit image job using the six positional inputs from the Z-Image OpenAPI schema.
    event_id = await submit_zimage(
        {
            "data": [
                image_request.prompt,
                image_request.resolution,
                image_request.seed,
                image_request.steps,
                image_request.shift,
                image_request.random_seed,
            ]
        }
    )

    # The Z-Image endpoint returns its result through an SSE completion event.
    events = await get_zimage_events(event_id)
    if any(event.get("event") == "error" for event in events):
        raise HTTPException(502, "Z-Image reported a generation error.")

    completed = [event for event in events if event.get("event") == "complete"]
    if not completed:
        raise HTTPException(504, "Z-Image did not return a completion event before the wait limit.")

    image_files = []
    for event in completed:
        image_files.extend(_find_filedata(event.get("data")))

    image_file = next(
        (
            item for item in image_files
            if isinstance(item.get("url"), str) and item["url"].strip()
        ),
        None,
    )
    if not image_file:
        raise HTTPException(502, "Z-Image completed but did not return a downloadable image URL.")

    image_url = urljoin(settings.zimage_base_url.rstrip("/") + "/", image_file["url"])
    video_result = await generate_wan(_wan_payload(image_url, video_request))

    return ImageToVideoPipelineResponse(
        status="completed",
        image_event_id=event_id,
        image=image_file,
        video=video_result["output"],
    )


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
                "generation": "direct JSON request with FileData response",
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
    event_id = await submit_zimage(
        {
            "data": [
                request.prompt,
                request.resolution,
                request.seed,
                request.steps,
                request.shift,
                request.random_seed,
            ]
        }
    )
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
    if any(event.get("event") == "error" for event in events):
        raise HTTPException(502, "Z-Image reported a generation error.")
    complete_events = [event for event in events if event.get("event") == "complete"]
    outputs = []
    for event in complete_events:
        outputs.extend(_find_filedata(event.get("data")))
    return ImageJobResultResponse(
        event_id=event_id,
        status="completed" if complete_events else "pending",
        outputs=outputs,
        events=events,
    )


@app.post(
    "/api/v1/videos",
    response_model=VideoResultResponse,
    dependencies=[Depends(require_api_key)],
)
async def create_video(request: VideoRequest):
    result = await generate_wan(_wan_payload(str(request.input_image), request))
    return VideoResultResponse(output=result["output"], raw_response=result["raw_response"])


@app.post(
    "/api/v1/pipelines/image-to-video",
    response_model=ImageToVideoPipelineResponse,
    dependencies=[Depends(require_api_key)],
)
async def create_image_to_video_pipeline(request: ImageToVideoPipelineRequest):
    # This is a synchronous end-to-end request. Host it on a service that allows
    # long-running requests; a production queue/worker will replace this route later.
    return await _run_image_to_video(request.image, request.video)
