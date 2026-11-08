from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    users_base_url: AnyHttpUrl | None = None
    channels_base_url: AnyHttpUrl | None = None
    messages_base_url: AnyHttpUrl | None = None
    threads_base_url: AnyHttpUrl | None = None
    integrals_base_url: AnyHttpUrl | None = None
    polls_base_url: AnyHttpUrl | None = None
    http_timeout_seconds: float = Field(default=5, gt=0)
    cors_origins: list[str] = ["http://localhost:5173"]
