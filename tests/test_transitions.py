import subprocess

import pytest
from pydantic import ValidationError

from app import media
from app.schemas import MediaExportRequest, TransitionSettings
from app.storage import LocalStore


def test_crossfade_builds_sequential_filters_with_trim_aware_offsets(tmp_path, monkeypatch):
    clips = [tmp_path / "one.mp4", tmp_path / "two.mp4", tmp_path / "three.mp4"]
    output = tmp_path / "crossfade.mp4"
    for clip in clips:
        clip.write_bytes(b"video")
    monkeypatch.setattr(media.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(media, "probe_media", lambda path: {"format": {"duration": "8"}})
    captured = []

    def fake_run(command, **kwargs):
        captured.append(command)
        output.write_bytes(b"rendered")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(media.subprocess, "run", fake_run)
    media.assemble_video(
        clips, output, trim_ranges=[(1, 6), (0, 8), (2, 8)],
        transition_type="crossfade", transition_duration_seconds=1.0,
    )
    graph = captured[0][captured[0].index("-filter_complex") + 1]
    assert "xfade=transition=fade:duration=1.000:offset=4.000[vx1]" in graph
    assert "xfade=transition=fade:duration=1.000:offset=11.000[vx2]" in graph
    assert graph.count("xfade=") == 2


def test_crossfade_rejects_single_clip_and_too_short_clips(tmp_path, monkeypatch):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video")
    monkeypatch.setattr(media.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(media, "probe_media", lambda path: {"format": {"duration": "0.4"}})
    with pytest.raises(media.MediaError, match="at least two"):
        media.assemble_video([clip], tmp_path / "one.mp4", transition_type="crossfade")
    second = tmp_path / "second.mp4"
    second.write_bytes(b"video")
    with pytest.raises(media.MediaError, match="longer than"):
        media.assemble_video(
            [clip, second], tmp_path / "two.mp4",
            transition_type="crossfade", transition_duration_seconds=0.5,
        )


def test_transition_settings_validate_type_and_duration():
    assert TransitionSettings(type="crossfade", duration_seconds=1.2).type == "crossfade"
    with pytest.raises(ValidationError):
        TransitionSettings(type="wipe")
    with pytest.raises(ValidationError):
        TransitionSettings(type="crossfade", duration_seconds=3)


def test_export_job_persists_transition_settings(tmp_path):
    store = LocalStore(tmp_path / "studio")
    project = store.create_project("project-id", "Transition test")
    job = store.create_export_job({
        "id": "job-id", "project_id": project["id"], "asset_ids": ["video-id"],
        "profile": "vertical", "fps": 30,
        "transition": {"type": "crossfade", "duration_seconds": 0.8},
    })
    assert job["transition"] == {"type": "crossfade", "duration_seconds": 0.8}

def test_crossfade_shortens_audio_timeline_to_match_video(tmp_path, monkeypatch):
    clips = [tmp_path / "one.mp4", tmp_path / "two.mp4"]
    music = tmp_path / "music.mp3"
    output = tmp_path / "mixed-crossfade.mp4"
    for path in [*clips, music]:
        path.write_bytes(b"media")
    monkeypatch.setattr(media.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(media, "probe_media", lambda path: {"format": {"duration": "8"}})
    captured = []

    def fake_run(command, **kwargs):
        captured.append(command)
        output.write_bytes(b"rendered")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(media.subprocess, "run", fake_run)
    media.assemble_video(
        clips, output, music_path=music, transition_type="crossfade",
        transition_duration_seconds=1.0,
    )
    command = captured[0]
    duration_index = command.index("-t")
    assert command[duration_index + 1] == "15.000"
    graph = command[command.index("-filter_complex") + 1]
    assert "atrim=duration=15.000" in graph
