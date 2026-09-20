from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./webmonitor.db"
    default_check_interval: int = 60      # segundos
    failure_threshold: int = 3            # fallos seguidos para marcar DOWN
    request_timeout: float = 10.0
    discord_webhook_url: str | None = None
    api_key: str | None = None


settings = Settings()