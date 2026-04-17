"""Application configuration via Pydantic settings."""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
