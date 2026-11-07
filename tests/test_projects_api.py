from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def _configure(monkeypatch, tmp_path, max_upload_bytes=1024):
    monkeypatch.setattr(settings, "api_key", "test-secret")
    monkeypatch.setattr(settings, "allow_unauthenticated_generation", False)
    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "studio"))
    monkeypatch.setattr(settings, "max_upload_bytes", max_upload_bytes)
    return TestClient(app), {"X-API-Key": "test-secret"}


def test_project_create_upload_and_list_assets(tmp_path, monkeypatch):
    client, headers = _configure(monkeypatch, tmp_path)
    project_response = client.post(
        "/api/v1/projects",
        json={"title": "  FINOMICS launch  "},
        headers=headers,
    )
    assert project_response.status_code == 200
    project = project_response.json()
    assert project["title"] == "FINOMICS launch"

    png = bytes.fromhex("89504E470D0A1A0A") + b"test-image"
    upload_response = client.post(
        f"/api/v1/projects/{project['id']}/assets",
        headers=headers,
        files={"file": ("scene.png", png, "image/png")},
    )
    assert upload_response.status_code == 200
    asset = upload_response.json()
    assert asset["original_name"] == "scene.png"
    assert asset["size_bytes"] == len(png)
    assert len(asset["sha256"]) == 64

    listing = client.get(
        f"/api/v1/projects/{project['id']}/assets",
        headers=headers,
    )
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [asset["id"]]


def test_project_routes_require_api_key(tmp_path, monkeypatch):
    client, _ = _configure(monkeypatch, tmp_path)
    response = client.get("/api/v1/projects")
    assert response.status_code == 401


def test_project_title_cannot_be_only_whitespace(tmp_path, monkeypatch):
    client, headers = _configure(monkeypatch, tmp_path)
    response = client.post(
        "/api/v1/projects",
        json={"title": "   "},
        headers=headers,
    )
    assert response.status_code == 422


def test_asset_upload_rejects_mismatched_file_signature(tmp_path, monkeypatch):
    client, headers = _configure(monkeypatch, tmp_path)
    project = client.post(
        "/api/v1/projects",
        json={"title": "Test"},
        headers=headers,
    ).json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/assets",
        headers=headers,
        files={"file": ("fake.png", b"not a png", "image/png")},
    )
    assert response.status_code == 415


def test_asset_upload_enforces_size_limit(tmp_path, monkeypatch):
    client, headers = _configure(monkeypatch, tmp_path, max_upload_bytes=8)
    project = client.post(
        "/api/v1/projects",
        json={"title": "Test"},
        headers=headers,
    ).json()
    png = bytes.fromhex("89504E470D0A1A0A") + b"too-large"
    response = client.post(
        f"/api/v1/projects/{project['id']}/assets",
        headers=headers,
        files={"file": ("large.png", png, "image/png")},
    )
    assert response.status_code == 413
