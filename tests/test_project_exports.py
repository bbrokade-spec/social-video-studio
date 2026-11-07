from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "api_key", "test-secret")
    monkeypatch.setattr(settings, "allow_unauthenticated_generation", False)
    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "studio"))
    return TestClient(app), {"X-API-Key": "test-secret"}


def _create_project_and_video(client, headers, filename="clip.mp4"):
    project = client.post(
        "/api/v1/projects",
        json={"title": "Export test"},
        headers=headers,
    ).json()
    mp4 = b"\x00\x00\x00\x18ftypisom" + b"fake-video-content"
    uploaded = client.post(
        f"/api/v1/projects/{project['id']}/assets",
        headers=headers,
        files={"file": (filename, mp4, "video/mp4")},
    )
    assert uploaded.status_code == 200
    return project, uploaded.json()


def test_export_uses_only_selected_project_video_assets(tmp_path, monkeypatch):
    client, headers = _client(monkeypatch, tmp_path)
    project, asset = _create_project_and_video(client, headers)

    def fake_assemble(clips, output_path, **kwargs):
        assert len(clips) == 1
        assert kwargs["profile"] == "vertical"
        output_path.write_bytes(b"rendered-mp4")
        return output_path

    monkeypatch.setattr("app.main.assemble_video", fake_assemble)
    response = client.post(
        f"/api/v1/projects/{project['id']}/exports",
        headers=headers,
        json={"asset_ids": [asset["id"]], "profile": "vertical", "fps": 30},
    )
    assert response.status_code == 200
    exported = response.json()
    assert exported["media_type"] == "video/mp4"
    assert exported["original_name"] == "export-vertical.mp4"

    download = client.get(
        f"/api/v1/assets/{exported['id']}/download",
        headers=headers,
    )
    assert download.status_code == 200
    assert download.content == b"rendered-mp4"


def test_export_rejects_image_assets(tmp_path, monkeypatch):
    client, headers = _client(monkeypatch, tmp_path)
    project = client.post(
        "/api/v1/projects",
        json={"title": "Export test"},
        headers=headers,
    ).json()
    png = bytes.fromhex("89504E470D0A1A0A") + b"image"
    asset = client.post(
        f"/api/v1/projects/{project['id']}/assets",
        headers=headers,
        files={"file": ("cover.png", png, "image/png")},
    ).json()

    response = client.post(
        f"/api/v1/projects/{project['id']}/exports",
        headers=headers,
        json={"asset_ids": [asset["id"]]},
    )
    assert response.status_code == 422


def test_export_rejects_asset_from_another_project(tmp_path, monkeypatch):
    client, headers = _client(monkeypatch, tmp_path)
    project_a, asset = _create_project_and_video(client, headers)
    project_b = client.post(
        "/api/v1/projects",
        json={"title": "Different project"},
        headers=headers,
    ).json()

    response = client.post(
        f"/api/v1/projects/{project_b['id']}/exports",
        headers=headers,
        json={"asset_ids": [asset["id"]]},
    )
    assert response.status_code == 404
