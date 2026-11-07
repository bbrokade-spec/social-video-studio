import subprocess

import pytest
from pydantic import ValidationError

from app import media
from app.schemas import MediaExportRequest
from app.storage import LocalStore


def test_trim_ranges_become_ffmpeg_input_seek_and_duration(tmp_path, monkeypatch):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video")
    output = tmp_path / "trimmed.mp4"
    monkeypatch.setattr(media.shutil, "which", lambda name: f"/usr/bin/{name}")
    captured = []

    def fake_run(command, **kwargs):
        captured.append(command)
        output.write_bytes(b"rendered")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(media.subprocess, "run", fake_run)
    media.assemble_video([clip], output, trim_ranges=[(2.5, 7.0)])

    command = captured[0]
    input_index = command.index("-i")
    assert command[input_index - 4:input_index] == ["-ss", "2.500", "-t", "4.500"]


def test_trim_ranges_reject_invalid_values(tmp_path, monkeypatch):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video")
    monkeypatch.setattr(media.shutil, "which", lambda name: f"/usr/bin/{name}")
    with pytest.raises(media.MediaError, match="end time"):
        media.assemble_video([clip], tmp_path / "out.mp4", trim_ranges=[(5, 4)])
    with pytest.raises(media.MediaError, match="finite"):
        media.assemble_video([clip], tmp_path / "out.mp4", trim_ranges=[(float("nan"), None)])
    with pytest.raises(media.MediaError, match="one trim range"):
        media.assemble_video([clip], tmp_path / "out.mp4", trim_ranges=[])


def test_export_request_validates_clip_trim_order_and_bounds():
    request = MediaExportRequest(
        asset_ids=["a", "b"],
        clip_trims=[
            {"asset_id": "a", "start_seconds": 1, "end_seconds": 3},
            {"asset_id": "b", "start_seconds": 0},
        ],
    )
    assert request.clip_trims[0].end_seconds == 3
    with pytest.raises(ValidationError):
        MediaExportRequest(
            asset_ids=["a", "b"],
            clip_trims=[{"asset_id": "b"}, {"asset_id": "a"}],
        )
    with pytest.raises(ValidationError):
        MediaExportRequest(
            asset_ids=["a"],
            clip_trims=[{"asset_id": "a", "start_seconds": 4, "end_seconds": 3}],
        )


def test_export_job_persists_clip_trims_and_migrates_old_database(tmp_path):
    store = LocalStore(tmp_path / "studio")
    project = store.create_project("project-id", "Trim test")
    job = store.create_export_job({
        "id": "job-id",
        "project_id": project["id"],
        "asset_ids": ["asset-a"],
        "clip_trims": [{"asset_id": "asset-a", "start_seconds": 2, "end_seconds": 5}],
        "profile": "vertical",
        "fps": 30,
    })
    assert job["clip_trims"] == [
        {"asset_id": "asset-a", "start_seconds": 2, "end_seconds": 5}
    ]

