from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    secret_key: str = "change-me"
    session_expire_minutes: int = 60 * 24 * 7

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "gms_world_foods"
    db_user: str = "postgres"
    db_password: str = ""
    db_ssl: str = ""  # set to "require" for Neon / other managed Postgres

    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    cloudinary_upload_preset: str = "GMS_WORLD_FOODS"
    cloudinary_folder: str = "gms-world-foods"

    cors_origins: str = "http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:3000,http://localhost:3000"

    @property
    def cloudinary_configured(self) -> bool:
        return bool(self.cloudinary_cloud_name and self.cloudinary_api_key and self.cloudinary_api_secret)

    @property
    def database_url(self) -> str:
        base = (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )
        if self.db_ssl:
            return f"{base}?ssl={self.db_ssl}"
        return base

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.app_env.lower() == "production":
            weak = {"", "change-me", "change-me-to-a-long-random-string"}
            if self.secret_key in weak or len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY must be a non-default value of at least 32 characters in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
