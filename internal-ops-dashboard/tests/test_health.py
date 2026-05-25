import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "running"


def test_health_check():
    r = client.get("/health/")
    assert r.status_code == 200
    data = r.json()
    assert data["overall"] in ("healthy", "degraded", "down")
    assert "total_services" in data


def test_services_list():
    r = client.get("/health/services")
    assert r.status_code == 200
    assert isinstance(r.json()["services"], list)


def test_service_not_found():
    r = client.get("/health/services/does-not-exist")
    assert r.status_code == 404


def test_patch_service_status():
    r = client.patch("/health/services/api-gateway?status=degraded&notes=test+override")
    assert r.status_code == 200
    assert r.json()["status"] == "degraded"

    # restore
    client.patch("/health/services/api-gateway?status=healthy")


def test_simulate_latency():
    r = client.get("/simulate/latency?ms=10")
    assert r.status_code == 200


def test_simulate_crash():
    r = client.get("/simulate/crash")
    assert r.status_code == 500