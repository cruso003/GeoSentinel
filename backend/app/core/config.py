"""Application configuration via Pydantic settings."""

from functools import lru_cache
from typing import List

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Values we refuse to start with in production. These are the defaults shipped
# in the repo so a misconfigured deploy fails fast instead of booting with a
# known-weak secret.
_UNSAFE_JWT_SECRETS = {
    "dev-secret-please-replace-please-please",
    "change-me",
    "secret",
    "",
}
_UNSAFE_INFLUX_TOKENS = {"devtoken", "change-me", ""}
_UNSAFE_GATEWAY_KEYS = {"replace-with-gateway-key", "change-me", ""}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = Field(default="postgresql+asyncpg://geosentinel:geosentinel@localhost:5432/geosentinel")
    influxdb_url: str = Field(default="http://localhost:8086")
    influxdb_token: str = Field(default="devtoken")
    influxdb_org: str = Field(default="geosentinel")
    influxdb_bucket: str = Field(default="sensor_data")

    # Auth
    jwt_secret_key: str = Field(default="dev-secret-please-replace-please-please")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60)
    refresh_token_expire_days: int = Field(default=30)
    max_password_bytes: int = Field(default=72)  # bcrypt silently truncates beyond this.

    # Redis / Celery
    redis_url: str = Field(default="redis://localhost:6379/0")
    celery_broker_url: str = Field(default="redis://localhost:6379/1")

    # MQTT
    mqtt_broker_host: str = Field(default="localhost")
    mqtt_broker_port: int = Field(default=1883)
    mqtt_gateway_api_key: str = Field(default="replace-with-gateway-key")

    # ESA Copernicus
    esa_dhus_username: str = Field(default="")
    esa_dhus_password: str = Field(default="")

    # Notifications
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    twilio_account_sid: str = Field(default="")
    twilio_auth_token: str = Field(default="")
    twilio_from_number: str = Field(default="")

    # App
    env: str = Field(default="development")
    allowed_origins: str = Field(default="http://localhost:5173")
    enable_mock_stream: bool = Field(default=True)

    # Cookie-based refresh flow (Phase 2.1 §10).
    refresh_cookie_name: str = Field(default="gs_refresh")
    refresh_cookie_path: str = Field(default="/api/v1/auth")
    csrf_cookie_name: str = Field(default="gs_csrf")
    csrf_header_name: str = Field(default="X-CSRF-Token")

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.env.lower() in ("production", "prod")

    @model_validator(mode="after")
    def _enforce_prod_hardening(self) -> "Settings":
        if not self.is_production:
            return self
        errs: list[str] = []
        if self.jwt_secret_key.strip() in _UNSAFE_JWT_SECRETS:
            errs.append("jwt_secret_key is unset or matches a known-weak default")
        if len(self.jwt_secret_key) < 32:
            errs.append("jwt_secret_key must be at least 32 characters in production")
        if self.influxdb_token.strip() in _UNSAFE_INFLUX_TOKENS:
            errs.append("influxdb_token is unset or matches a known-weak default")
        if self.mqtt_gateway_api_key.strip() in _UNSAFE_GATEWAY_KEYS:
            errs.append("mqtt_gateway_api_key is unset or matches a known-weak default")
        if not self.cors_origins:
            errs.append("allowed_origins must list at least one HTTPS origin in production")
        for origin in self.cors_origins:
            if origin.startswith("http://") and "localhost" not in origin:
                errs.append(f"allowed_origins entry {origin!r} must use HTTPS in production")
        if errs:
            raise ValueError(
                "Refusing to boot with unsafe production configuration:\n  - "
                + "\n  - ".join(errs)
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
