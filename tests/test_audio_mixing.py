import subprocess

import pytest
from pydantic import ValidationError

from app import media
from app.schemas import AudioMixSettings, MediaExportRequest
from app.storage import LocalStore


def test_audio_mix_adds_voiceover_and_looped_music_inputs(tmp_path, monkeypatch):
    clip = tmp_path / "clip.mp4"
    voice = tmp_path / "voice.wav"
    music = tmp_path / "music.mp3"
    output = tmp_path / "mixed.mp4"
    for path in (clip, voice, music):
        path.write_bytes(b"media")
    monkeypatch.setattr(media.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(media, "probe_media", lambda path: {"format": {"duration": "10"}})
    captured = []

    def fake_run(command, **kwargs):
        captured.append(command)
        output.write_bytes(b"rendered")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(media.subprocess, "run", fake_run)
    media.assemble_video(
        [clip], output, voiceover_path=voice, music_path=music,
        voiceover_volume=1, music_volume=0.2, fade_in_seconds=0.5, fade_out_seconds=1,
    )
    command = captured[0]
    assert command.count("-i") == 3
    music_index = command.index(str(music))
    assert command[music_index - 2:music_index] == ["-stream_loop", "-1"]
    filter_graph = command[command.index("-filter_complex") + 1]
    assert "amix=inputs=2" in filter_graph
    assert "atrim=duration=10.000" in filter_graph
    assert "volume=0.2000" in filter_graph
    assert "-c:a" in command and "aac" in command
    assert "-shortest" not in command
    assert command[command.index("-t") + 1] == "10.000"


def test_audio_mix_rejects_invalid_volume_and_fades(tmp_path, monkeypatch):
    clip = tmp_path / "clip.mp4"
    voice = tmp_path / "voice.wav"
    clip.write_bytes(b"video")
    voice.write_bytes(b"audio")
    monkeypatch.setattr(media.shutil, "which", lambda name: f"/usr/bin/{name}")
    with pytest.raises(media.MediaError, match="volume"):
        media.assemble_video([clip], tmp_path / "out.mp4", voiceover_path=voice, voiceover_volume=3)
    with pytest.raises(media.MediaError, match="fade"):
        media.assemble_video([clip], tmp_path / "out.mp4", voiceover_path=voice, fade_out_seconds=11)


def test_audio_schema_enforces_safe_ranges_and_export_accepts_audio():
    settings = AudioMixSettings(voiceover_volume=1.2, music_volume=0.15, fade_in_seconds=0, fade_out_seconds=2)
    request = MediaExportRequest(asset_ids=["video-id"], audio=settings)
    assert request.audio.music_volume == 0.15
    with pytest.raises(ValidationError):
        AudioMixSettings(music_volume=2.1)
    with pytest.raises(ValidationError):
        AudioMixSettings(fade_in_seconds=-1)


def test_export_job_round_trips_audio_settings(tmp_path):
    store = LocalStore(tmp_path / "studio")
    project = store.create_project("project-id", "Audio test")
    job = store.create_export_job({
        "id": "job-id", "project_id": project["id"], "asset_ids": ["video-id"],
        "profile": "vertical", "fps": 30,
        "audio": {"voiceover_asset_id": "voice-id", "music_volume": 0.2},
    })
    assert job["audio"] == {"voiceover_asset_id": "voice-id", "music_volume": 0.2}
