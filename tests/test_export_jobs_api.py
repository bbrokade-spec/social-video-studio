from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_export_job_api_queues_and_reads_status(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-secret")
    monkeypatch.setattr(settings, "allow_unauthenticated_generation", False)
    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "studio"))
    monkeypatch.setattr("app.main._process_next_export_job", lambda: False)
    headers = {"X-API-Key": "test-secret"}

    with TestClient(app) as client:
        project = client.post(
            "/api/v1/projects", json={"title": "Queued export"}, headers=headers
        ).json()
        mp4 = b"\x00\x00\x00\x18ftypisom" + b"fake-video"
        asset = client.post(
            f"/api/v1/projects/{project['id']}/assets",
            headers=headers,
            files={"file": ("clip.mp4", mp4, "video/mp4")},
        ).json()

        response = client.post(
            f"/api/v1/projects/{project['id']}/export-jobs",
            headers=headers,
            json={"asset_ids": [asset["id"]], "profile": "vertical", "fps": 30},
        )
        assert response.status_code == 202
        job = response.json()
        assert job["status"] == "queued"
        assert job["progress"] == 0

        status = client.get(f"/api/v1/export-jobs/{job['id']}", headers=headers)
        assert status.status_code == 200
        assert status.json()["id"] == job["id"]


def test_export_job_api_rejects_missing_api_key(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-secret")
    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "studio"))
    with TestClient(app) as client:
        response = client.get("/api/v1/export-jobs/not-a-real-id")
        assert response.status_code == 401
