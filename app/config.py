from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./widgets.db"
    secret_key: str = "dev-only-change-me"
    allowed_origins: str = "http://localhost:5500,http://localhost:8080"
    geo_provider_a_url: str = "http://ip-api.com/json"
    geo_provider_b_url: str = "https://ipapi.co"
    rate_limit_per_minute: int = 20
    smtp_enabled: bool = False
    public_base_url: str = "http://localhost:8000"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
