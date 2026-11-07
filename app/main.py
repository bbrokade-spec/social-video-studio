from urllib.parse import urljoin
import hashlib
import secrets
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Security, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from starlette.concurrency import run_in_threadpool
from fastapi.security.api_key import APIKeyHeader

from .config import settings
from .storage import LocalStore, StorageError
from .media import MediaError, assemble_video
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
    ProjectCreateRequest,
    ProjectResponse,
    AssetResponse,
    MediaExportRequest,
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


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def studio_home():
    interface = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(interface.read_text(encoding="utf-8"))


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


_ALLOWED_UPLOADS = {
    ".mp4": {"video/mp4"},
    ".mov": {"video/quicktime"},
    ".webm": {"video/webm"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
    ".mp3": {"audio/mpeg"},
    ".wav": {"audio/wav", "audio/x-wav"},
    ".m4a": {"audio/mp4", "audio/x-m4a"},
}


def _store() -> LocalStore:
    return LocalStore(settings.data_dir)


def _matches_media_signature(extension: str, header: bytes) -> bool:
    if extension in {".mp4", ".mov", ".m4a"}:
        return len(header) >= 12 and header[4:8] == b"ftyp"
    if extension == ".webm":
        return header.startswith(bytes.fromhex("1A45DFA3"))
    if extension in {".jpg", ".jpeg"}:
        return header.startswith(bytes.fromhex("FFD8FF"))
    if extension == ".png":
        return header.startswith(bytes.fromhex("89504E470D0A1A0A"))
    if extension == ".webp":
        return len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    if extension == ".wav":
        return len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WAVE"
    if extension == ".mp3":
        return header.startswith(b"ID3") or (
            len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0
        )
    return False


@app.post(
    "/api/v1/projects",
    response_model=ProjectResponse,
    dependencies=[Depends(require_api_key)],
)
async def create_project(request: ProjectCreateRequest):
    project_id = str(uuid.uuid4())
    try:
        return _store().create_project(project_id, request.title.strip())
    except Exception as exc:
        raise HTTPException(500, "Could not create the project.") from exc


@app.get(
    "/api/v1/projects",
    response_model=list[ProjectResponse],
    dependencies=[Depends(require_api_key)],
)
async def list_projects():
    return _store().list_projects()


@app.post(
    "/api/v1/projects/{project_id}/assets",
    response_model=AssetResponse,
    dependencies=[Depends(require_api_key)],
)
async def upload_project_asset(project_id: str, file: UploadFile = File(...)):
    try:
        project_id = str(uuid.UUID(project_id))
    except ValueError as exc:
        raise HTTPException(404, "Project not found.") from exc

    store = _store()
    if not store.get_project(project_id):
        raise HTTPException(404, "Project not found.")

    supplied_name = (file.filename or "upload").replace("\\", "/").split("/")[-1]
    extension = Path(supplied_name).suffix.lower()
    media_type = (file.content_type or "").lower()
    if extension not in _ALLOWED_UPLOADS or media_type not in _ALLOWED_UPLOADS[extension]:
        raise HTTPException(415, "Unsupported file type or mismatched media type.")

    asset_id = str(uuid.uuid4())
    stored_name = f"{asset_id}{extension}"
    temporary_path = store.asset_dir / f".{asset_id}.upload"
    final_path = store.asset_dir / stored_name
    digest = hashlib.sha256()
    size = 0
    header = b""

    try:
        with temporary_path.open("xb") as destination:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                if not header:
                    header = chunk[:16]
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(413, "Upload exceeds the configured size limit.")
                digest.update(chunk)
                destination.write(chunk)

        if size == 0:
            raise HTTPException(400, "Uploaded file is empty.")
        if not _matches_media_signature(extension, header):
            raise HTTPException(415, "File content does not match its declared media type.")

        temporary_path.replace(final_path)
        asset = store.register_asset({
            "id": asset_id,
            "project_id": project_id,
            "original_name": supplied_name[:255],
            "stored_name": stored_name,
            "media_type": media_type,
            "size_bytes": size,
            "sha256": digest.hexdigest(),
        })
        return {key: asset[key] for key in (
            "id", "project_id", "original_name", "media_type",
            "size_bytes", "sha256", "created_at"
        )}
    except HTTPException:
        temporary_path.unlink(missing_ok=True)
        final_path.unlink(missing_ok=True)
        raise
    except (OSError, StorageError) as exc:
        temporary_path.unlink(missing_ok=True)
        final_path.unlink(missing_ok=True)
        raise HTTPException(500, "Could not store the uploaded asset.") from exc
    finally:
        await file.close()


@app.get(
    "/api/v1/projects/{project_id}/assets",
    response_model=list[AssetResponse],
    dependencies=[Depends(require_api_key)],
)
async def list_project_assets(project_id: str):
    try:
        project_id = str(uuid.UUID(project_id))
    except ValueError as exc:
        raise HTTPException(404, "Project not found.") from exc
    store = _store()
    if not store.get_project(project_id):
        raise HTTPException(404, "Project not found.")
    return [
        {key: asset[key] for key in (
            "id", "project_id", "original_name", "media_type",
            "size_bytes", "sha256", "created_at"
        )}
        for asset in store.list_assets(project_id)
    ]


@app.post(
    "/api/v1/projects/{project_id}/exports",
    response_model=AssetResponse,
    dependencies=[Depends(require_api_key)],
)
async def export_project_video(project_id: str, request: MediaExportRequest):
    try:
        project_id = str(uuid.UUID(project_id))
    except ValueError as exc:
        raise HTTPException(404, "Project not found.") from exc

    store = _store()
    if not store.get_project(project_id):
        raise HTTPException(404, "Project not found.")

    project_assets = {item["id"]: item for item in store.list_assets(project_id)}
    if len(set(request.asset_ids)) != len(request.asset_ids):
        raise HTTPException(422, "Duplicate asset IDs are not allowed.")

    selected = []
    for asset_id in request.asset_ids:
        asset = project_assets.get(asset_id)
        if not asset:
            raise HTTPException(404, "One or more project assets were not found.")
        if asset["media_type"] != "video/mp4" and not (
            asset["media_type"] in {"video/quicktime", "video/webm"}
        ):
            raise HTTPException(422, "Only video assets can be included in an export.")
        stored_name = asset["stored_name"]
        if Path(stored_name).name != stored_name:
            raise HTTPException(500, "Stored asset metadata is invalid.")
        source = (store.asset_dir / stored_name).resolve()
        if source.parent != store.asset_dir.resolve() or not source.is_file():
            raise HTTPException(404, "A project media file is missing.")
        selected.append(source)

    asset_id = str(uuid.uuid4())
    stored_name = f"{asset_id}.mp4"
    output_path = store.asset_dir / stored_name
    try:
        await run_in_threadpool(
            assemble_video,
            selected,
            output_path,
            profile=request.profile,
            fps=request.fps,
        )
        digest = hashlib.sha256()
        with output_path.open("rb") as rendered:
            for chunk in iter(lambda: rendered.read(1024 * 1024), b""):
                digest.update(chunk)
        asset = store.register_asset({
            "id": asset_id,
            "project_id": project_id,
            "original_name": f"export-{request.profile}.mp4",
            "stored_name": stored_name,
            "media_type": "video/mp4",
            "size_bytes": output_path.stat().st_size,
            "sha256": digest.hexdigest(),
        })
        return {key: asset[key] for key in (
            "id", "project_id", "original_name", "media_type",
            "size_bytes", "sha256", "created_at"
        )}
    except MediaError as exc:
        output_path.unlink(missing_ok=True)
        raise HTTPException(422, str(exc)) from exc
    except (OSError, StorageError) as exc:
        output_path.unlink(missing_ok=True)
        raise HTTPException(500, "Could not save the exported video.") from exc


@app.get(
    "/api/v1/assets/{asset_id}/download",
    dependencies=[Depends(require_api_key)],
)
async def download_project_asset(asset_id: str):
    try:
        asset_id = str(uuid.UUID(asset_id))
    except ValueError as exc:
        raise HTTPException(404, "Asset not found.") from exc
    store = _store()
    asset = store.get_asset(asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found.")
    stored_name = asset["stored_name"]
    if Path(stored_name).name != stored_name:
        raise HTTPException(500, "Stored asset metadata is invalid.")
    source = (store.asset_dir / stored_name).resolve()
    if source.parent != store.asset_dir.resolve() or not source.is_file():
        raise HTTPException(404, "Asset file not found.")
    return FileResponse(
        source,
        media_type=asset["media_type"],
        filename=asset["original_name"],
    )
