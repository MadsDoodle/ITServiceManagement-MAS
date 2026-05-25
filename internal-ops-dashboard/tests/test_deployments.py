from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_list_deployments():
    r = client.get("/deployments/")
    assert r.status_code == 200
    assert "deployments" in r.json()


def test_latest_deployment():
    r = client.get("/deployments/latest")
    assert r.status_code == 200
    assert "deployment_id" in r.json()


def test_create_and_update_deployment():
    r = client.post("/deployments/", json={
        "version": "v9.9.9-test",
        "commit_ref": "aabbcc",
        "deployed_by": "pytest",
        "notes": "Test deployment",
    })
    assert r.status_code == 200
    dep_id = r.json()["deployment_id"]
    assert r.json()["status"] == "pending"

    r = client.patch(f"/deployments/{dep_id}", json={
        "status": "success",
        "duration_seconds": 42.0,
    })
    assert r.status_code == 200
    assert r.json()["status"] == "success"


def test_deployment_not_found():
    r = client.get("/deployments/dep-does-not-exist")
    assert r.status_code == 404