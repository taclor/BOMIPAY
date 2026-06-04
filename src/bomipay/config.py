from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    environment: str = Field("development", alias="BOMIPAY_ENV")
    database_url: str = Field("sqlite+aiosqlite:///./bomipay.db", alias="DATABASE_URL")
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")
    secret_key: str = Field(..., alias="SECRET_KEY")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    jwt_access_token_expire_seconds: int = Field(900, alias="JWT_ACCESS_TOKEN_EXPIRE_SECONDS")
    jwt_refresh_token_expire_seconds: int = Field(604800, alias="JWT_REFRESH_TOKEN_EXPIRE_SECONDS")
    provider_encryption_key: str | None = Field(None, alias="PROVIDER_ENCRYPTION_KEY")
    cors_allowed_origins: str = Field(
        "http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ALLOWED_ORIGINS",
    )
    sentry_dsn: str | None = Field(None, alias="SENTRY_DSN")
    rate_limit_enabled: bool = Field(True, alias="RATE_LIMIT_ENABLED")
    docs_enabled: bool = Field(True, alias="DOCS_ENABLED")
    max_upload_size_bytes: int = Field(10 * 1024 * 1024, alias="MAX_UPLOAD_SIZE_BYTES")
    # Production hardening
    hsts_max_age: int = Field(31536000, alias="HSTS_MAX_AGE")  # 1 year
    csp_enabled: bool = Field(True, alias="CSP_ENABLED")
    request_logging_enabled: bool = Field(True, alias="REQUEST_LOGGING_ENABLED")

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


settings = AppSettings()
