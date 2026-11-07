from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class ImageRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=6000)
    resolution: str = "720x1280 ( 9:16 )"
    steps: int = Field(default=8, ge=1, le=100)
    shift: float = Field(default=3.0, ge=0, le=20)
    seed: int = Field(default=42, ge=0, le=2147483647)
    random_seed: bool = True


class VideoSettings(BaseModel):
    prompt: str = Field(min_length=3, max_length=6000)
    negative_prompt: str | None = None
    duration_seconds: float = Field(default=2.0, ge=0.5, le=5.0)
    steps: int = Field(default=6, ge=4, le=8)
    guidance_scale: float = Field(default=1.0, ge=0, le=10)
    guidance_scale_2: float = Field(default=1.0, ge=0, le=10)
    seed: int = Field(default=42, ge=0, le=2147483647)
    randomize_seed: bool = True


class VideoRequest(VideoSettings):
    input_image: HttpUrl


class ImageToVideoPipelineRequest(BaseModel):
    image: ImageRequest
    video: VideoSettings


class ImageJobSubmitResponse(BaseModel):
    provider: Literal["z-image-turbo"] = "z-image-turbo"
    event_id: str
    status: str
    detail: str


class ImageJobResultResponse(BaseModel):
    provider: Literal["z-image-turbo"] = "z-image-turbo"
    event_id: str
    status: str
    outputs: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)


class VideoResultResponse(BaseModel):
    provider: Literal["wan-2.2"] = "wan-2.2"
    status: Literal["completed"] = "completed"
    output: dict[str, Any]
    raw_response: dict[str, Any]


class ImageToVideoPipelineResponse(BaseModel):
    status: Literal["completed"] = "completed"
    image_event_id: str
    image: dict[str, Any]
    video: dict[str, Any]


class ProjectCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class ProjectResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class AssetResponse(BaseModel):
    id: str
    project_id: str
    original_name: str
    media_type: str
    size_bytes: int
    sha256: str
    created_at: str
