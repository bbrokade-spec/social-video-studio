from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    hf_token: str = ""
    api_key: str = ""
    allow_unauthenticated_generation: bool = False

    zimage_base_url: str = "https://mcp-tools-z-image-turbo.hf.space"
    wan_base_url: str = "https://zerogpu-aoti-wan2-2-fp8da-aoti-faster.hf.space"

    http_timeout_seconds: float = 60.0
    generation_wait_seconds: int = 240


settings = Settings()
