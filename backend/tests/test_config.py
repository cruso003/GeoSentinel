"""Production config validator (Phase 2.1 §1)."""

import pytest

from app.core.config import Settings


def _prod_kwargs(**overrides):
    base = dict(
        env="production",
        jwt_secret_key="a" * 40,
        influxdb_token="realtoken-abc123",
        mqtt_gateway_api_key="gateway-abc123",
        allowed_origins="https://geosentinel.example.com",
        model_signing_pubkey="00" * 32,
        report_signing_pubkey="11" * 32,
        report_signing_privkey_path="/srv/keys/report_signing.pem",
        enable_synthetic_ai_fallback=False,
    )
    base.update(overrides)
    return base


def test_production_rejects_default_jwt_secret():
    with pytest.raises(ValueError, match="jwt_secret_key"):
        Settings(**_prod_kwargs(jwt_secret_key="dev-secret-please-replace-please-please"))


def test_production_rejects_short_jwt_secret():
    with pytest.raises(ValueError, match="32 characters"):
        Settings(**_prod_kwargs(jwt_secret_key="short"))


def test_production_rejects_default_influx_token():
    with pytest.raises(ValueError, match="influxdb_token"):
        Settings(**_prod_kwargs(influxdb_token="devtoken"))


def test_production_rejects_default_gateway_key():
    with pytest.raises(ValueError, match="mqtt_gateway_api_key"):
        Settings(**_prod_kwargs(mqtt_gateway_api_key="replace-with-gateway-key"))


def test_production_rejects_empty_cors():
    with pytest.raises(ValueError, match="allowed_origins"):
        Settings(**_prod_kwargs(allowed_origins=""))


def test_production_rejects_http_origin():
    with pytest.raises(ValueError, match="HTTPS"):
        Settings(**_prod_kwargs(allowed_origins="http://geosentinel.example.com"))


def test_production_allows_localhost_http_for_smoke_tests():
    s = Settings(**_prod_kwargs(allowed_origins="https://prod.example.com,http://localhost:5173"))
    assert "http://localhost:5173" in s.cors_origins


def test_production_rejects_missing_model_signing_pubkey():
    with pytest.raises(ValueError, match="model_signing_pubkey"):
        Settings(**_prod_kwargs(model_signing_pubkey=""))


def test_production_rejects_missing_report_signing_pubkey():
    with pytest.raises(ValueError, match="report_signing_pubkey"):
        Settings(**_prod_kwargs(report_signing_pubkey=""))


def test_production_rejects_missing_report_signing_privkey_path():
    with pytest.raises(ValueError, match="report_signing_privkey_path"):
        Settings(**_prod_kwargs(report_signing_privkey_path=""))


def test_production_rejects_synthetic_ai_fallback():
    with pytest.raises(ValueError, match="enable_synthetic_ai_fallback"):
        Settings(**_prod_kwargs(enable_synthetic_ai_fallback=True))


def test_development_stays_permissive():
    s = Settings(env="development")
    assert s.jwt_secret_key == "dev-secret-please-replace-please-please"
    assert s.cors_origins == ["http://localhost:5173"]
    # Dev still shows the hour-of-day surrogate so a clean checkout is
    # not blank; prod validator above enforces the opposite.
    assert s.enable_synthetic_ai_fallback is True
