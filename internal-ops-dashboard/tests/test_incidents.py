import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_list_incidents():
    r = client.get("/incidents/")
    assert r.status_code == 200
    assert "incidents" in r.json()


def test_filter_by_severity():
    r = client.get("/incidents/?severity=critical")
    assert r.status_code == 200
    for inc in r.json()["incidents"]:
        assert inc["severity"] == "critical"


def test_filter_by_status():
    r = client.get("/incidents/?status=resolved")
    assert r.status_code == 200
    for inc in r.json()["incidents"]:
        assert inc["status"] == "resolved"


def test_create_incident():
    r = client.post("/incidents/", json={
        "title": "pytest test incident",
        "severity": "low",
        "affected_service": "test-service",
        "notes": "Created by test suite",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "pytest test incident"
    assert data["status"] == "open"
    return data["id"]


def test_create_and_resolve_incident():
    r = client.post("/incidents/", json={
        "title": "Lifecycle test incident",
        "severity": "medium",
        "affected_service": "api-gateway",
    })
    inc_id = r.json()["id"]

    r = client.patch(f"/incidents/{inc_id}", json={"status": "investigating", "notes": "Looking into it"})
    assert r.status_code == 200
    assert r.json()["status"] == "investigating"

    r = client.patch(f"/incidents/{inc_id}", json={"status": "resolved"})
    assert r.status_code == 200
    assert r.json()["status"] == "resolved"
    assert r.json()["resolved_at"] is not None


def test_incident_not_found():
    r = client.get("/incidents/999999")
    assert r.status_code == 404