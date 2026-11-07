import subprocess

import pytest
from pydantic import ValidationError

from app import media
from app.schemas import MediaExportRequest, SubtitleSettings
from app.storage import LocalStore


def test_srt_subtitles_are_burned_with_selected_style_and_position(tmp_path, monkeypatch):
    clip = tmp_path / "clip.mp4"
    subtitles = tmp_path / "captions.srt"
    output = tmp_path / "subtitled.mp4"
    clip.write_bytes(b"video")
    subtitles.write_text("1\\n00:00:00,000 --> 00:00:02,000\\nHello world\\n", encoding="utf-8")
    monkeypatch.setattr(media.shutil, "which", lambda name: f"/usr/bin/{name}")
    captured = []

    def fake_run(command, **kwargs):
        captured.append((command, kwargs))
        output.write_bytes(b"rendered")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(media.subprocess, "run", fake_run)
    media.assemble_video(
        [clip], output, subtitles_path=subtitles,
        subtitle_style="yellow", subtitle_position="center",
    )
    command, kwargs = captured[0]
    graph = command[command.index("-filter_complex") + 1]
    assert "subtitles=filename='captions.srt'" in graph
    assert "PrimaryColour=&H0000FFFF" in graph
    assert "Alignment=5" in graph
    assert kwargs["cwd"] == str(tmp_path)


def test_subtitle_source_and_preset_are_validated(tmp_path, monkeypatch):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video")
    monkeypatch.setattr(media.shutil, "which", lambda name: f"/usr/bin/{name}")
    with pytest.raises(media.MediaError, match="SRT"):
        media.assemble_video([clip], tmp_path / "out.mp4", subtitles_path=tmp_path / "missing.txt")
    with pytest.raises(media.MediaError, match="style"):
        media.assemble_video([clip], tmp_path / "out.mp4", subtitle_style="unknown")


def test_subtitle_schema_and_export_request():
    settings = SubtitleSettings(asset_id="caption-id", style="bold", position="center")
    request = MediaExportRequest(asset_ids=["video-id"], subtitles=settings)
    assert request.subtitles.style == "bold"
    with pytest.raises(ValidationError):
        SubtitleSettings(asset_id="caption-id", style="comic-sans")


def test_export_job_round_trips_subtitle_settings(tmp_path):
    store = LocalStore(tmp_path / "studio")
    project = store.create_project("project-id", "Subtitle test")
    job = store.create_export_job({
        "id": "job-id", "project_id": project["id"], "asset_ids": ["video-id"],
        "profile": "vertical", "fps": 30,
        "subtitles": {"asset_id": "srt-id", "style": "yellow", "position": "center"},
    })
    assert job["subtitles"] == {
        "asset_id": "srt-id", "style": "yellow", "position": "center"
    }
