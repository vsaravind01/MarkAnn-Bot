from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    backend_url: str = "http://localhost:8000"
    jwt_secret: str = "change-me-in-production-use-32-random-bytes"
    jwt_ttl_minutes: int = 15
    refresh_ttl_days: int = 30
    allowed_origins: str = "http://localhost:5173"
    https: bool = False
    trusted_gateway_secret: str = ""
    database_url: str = "sqlite+aiosqlite:///./markann.db"
    redis_url: str = "redis://localhost:6379/0"

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
