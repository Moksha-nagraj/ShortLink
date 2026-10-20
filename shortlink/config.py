from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://shortlink:shortlink@localhost:5432/shortlink"
    redis_url: str = "redis://localhost:6379/0"
    public_base_url: str = "http://localhost:8000"
    rate_limit_per_minute: int = 60
    cache_ttl_seconds: int = 300
    ip_hash_secret: str = "development-only"


settings = Settings()
