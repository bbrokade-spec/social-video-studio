from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


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

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project title cannot be blank.")
        return value


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


class ClipTrim(BaseModel):
    asset_id: str
    start_seconds: float = Field(default=0, ge=0, le=86400)
    end_seconds: float | None = Field(default=None, gt=0, le=86400)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_seconds is not None and self.end_seconds <= self.start_seconds:
            raise ValueError("Clip end time must be greater than its start time.")
        return self


class AudioMixSettings(BaseModel):
    voiceover_asset_id: str | None = None
    music_asset_id: str | None = None
    voiceover_volume: float = Field(default=1.0, ge=0, le=2)
    music_volume: float = Field(default=0.18, ge=0, le=2)
    fade_in_seconds: float = Field(default=0.5, ge=0, le=10)
    fade_out_seconds: float = Field(default=1.0, ge=0, le=10)


class SubtitleSettings(BaseModel):
    asset_id: str
    style: Literal["classic", "bold", "yellow"] = "classic"
    position: Literal["bottom", "center"] = "bottom"


class TransitionSettings(BaseModel):
    type: Literal["cut", "crossfade"] = "cut"
    duration_seconds: float = Field(default=0.5, ge=0.2, le=2.5)


class MediaExportRequest(BaseModel):
    asset_ids: list[str] = Field(min_length=1, max_length=50)
    profile: Literal["vertical", "landscape"] = "vertical"
    fps: int = Field(default=30, ge=1, le=60)
    clip_trims: list[ClipTrim] | None = None
    audio: AudioMixSettings | None = None
    subtitles: SubtitleSettings | None = None
    transition: TransitionSettings = Field(default_factory=TransitionSettings)

    @model_validator(mode="after")
    def validate_clip_trims(self):
        if self.clip_trims is not None:
            if len(self.clip_trims) != len(self.asset_ids):
                raise ValueError("Provide one trim setting for each selected clip.")
            if [item.asset_id for item in self.clip_trims] != self.asset_ids:
                raise ValueError("Clip trim settings must follow the selected clip order.")
        return self


class ExportJobCreateRequest(MediaExportRequest):
    pass


class ExportJobResponse(BaseModel):
    id: str
    project_id: str
    asset_ids: list[str]
    profile: Literal["vertical", "landscape"]
    fps: int
    status: Literal["queued", "running", "completed", "failed"]
    progress: int
    result_asset_id: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str
