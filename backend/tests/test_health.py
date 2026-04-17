from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"


def test_mohr_coulomb_demo() -> None:
    from ai.slopewatch.physics.mohr_coulomb import (
        Soil,
        demo_slices,
        factor_of_safety,
        risk_from_fos,
    )

    fos = factor_of_safety(demo_slices(), Soil(cohesion=15, friction_angle_deg=32))
    assert fos > 0.5
    risk = risk_from_fos(fos)
    assert 0.0 <= risk <= 1.0
