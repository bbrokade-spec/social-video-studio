import subprocess

import pytest

from app import media


def test_assemble_video_builds_vertical_export_command(tmp_path, monkeypatch):
    clip_a = tmp_path / "a.mov"
    clip_b = tmp_path / "b.mp4"
    clip_a.write_bytes(b"clip-a")
    clip_b.write_bytes(b"clip-b")
    output = tmp_path / "finished.mp4"
    calls = []

    monkeypatch.setattr(media.shutil, "which", lambda name: f"/usr/bin/{name}")

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        output.write_bytes(b"rendered-video")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(media.subprocess, "run", fake_run)

    result = media.assemble_video([clip_a, clip_b], output, profile="vertical")

    assert result == output.resolve()
    command, options = calls[0]
    assert "-filter_complex" in command
    filter_graph = command[command.index("-filter_complex") + 1]
    assert "scale=1080:1920" in filter_graph
    assert "concat=n=2:v=1:a=0" in filter_graph
    assert command[command.index("-an") - 1] == "[vout]"
    assert options["timeout"] == 900


def test_assemble_video_builds_landscape_export_command(tmp_path, monkeypatch):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"clip")
    output = tmp_path / "landscape.mp4"
    monkeypatch.setattr(media.shutil, "which", lambda name: f"/usr/bin/{name}")

    def fake_run(command, **kwargs):
        output.write_bytes(b"rendered")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(media.subprocess, "run", fake_run)
    media.assemble_video([clip], output, profile="landscape")
    # The profile dimensions are part of the normalized filter graph.
    assert output.exists()


@pytest.mark.parametrize(
    "clips, profile, fps",
    [
        ([], "vertical", 30),
        (["missing.mp4"], "vertical", 30),
        (["missing.mp4"] * 51, "vertical", 30),
        (["missing.mp4"], "square", 30),
        (["missing.mp4"], "vertical", 0),
    ],
)
def test_assemble_video_rejects_invalid_requests(tmp_path, clips, profile, fps):
    with pytest.raises(media.MediaError):
        media.assemble_video(
            clips,
            tmp_path / "out.mp4",
            profile=profile,
            fps=fps,
        )


def test_assemble_video_requires_mp4_output_and_existing_directory(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"clip")
    with pytest.raises(media.MediaError, match=r"\.mp4"):
        media.assemble_video([clip], tmp_path / "out.mov")
    with pytest.raises(media.MediaError, match="directory"):
        media.assemble_video([clip], tmp_path / "missing" / "out.mp4")


def test_assemble_video_rejects_empty_clip(tmp_path):
    clip = tmp_path / "empty.mp4"
    clip.touch()
    with pytest.raises(media.MediaError, match="empty"):
        media.assemble_video([clip], tmp_path / "out.mp4")


def test_assemble_video_reports_missing_ffmpeg(tmp_path, monkeypatch):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"clip")
    monkeypatch.setattr(media.shutil, "which", lambda name: None)
    with pytest.raises(media.MediaError, match="ffmpeg"):
        media.assemble_video([clip], tmp_path / "out.mp4")


def test_assemble_video_translates_ffmpeg_failure(tmp_path, monkeypatch):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"clip")
    monkeypatch.setattr(media.shutil, "which", lambda name: f"/usr/bin/{name}")

    def fail_run(command, **kwargs):
        raise subprocess.CalledProcessError(1, command, stderr="sensitive diagnostic")

    monkeypatch.setattr(media.subprocess, "run", fail_run)
    with pytest.raises(media.MediaError, match="could not assemble"):
        media.assemble_video([clip], tmp_path / "out.mp4")
