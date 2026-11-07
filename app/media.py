"""Local FFmpeg helpers for deterministic, silent video assembly.

This module deliberately contains no provider calls and no network access.
Audio mixing, subtitles, project manifests, and UI orchestration are separate layers.
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Literal, Sequence


class MediaError(RuntimeError):
    """Raised when a local media operation cannot be completed safely."""


ExportProfile = Literal["vertical", "landscape"]

PROFILES: dict[ExportProfile, tuple[int, int]] = {
    "vertical": (1080, 1920),
    "landscape": (1920, 1080),
}


def _executable(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise MediaError(f"{name} was not found on PATH. Install FFmpeg and restart the app.")
    return path


def probe_media(path: str | Path, *, timeout_seconds: int = 20) -> dict:
    """Return ffprobe's JSON metadata for an existing local media file."""
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise MediaError(f"Input media file does not exist: {source.name}")
    command = [
        _executable("ffprobe"),
        "-v", "error",
        "-show_entries", "format=duration,format_name:stream=codec_type,codec_name,width,height",
        "-of", "json",
        str(source),
    ]
    try:
        result = subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=timeout_seconds
        )
        metadata = json.loads(result.stdout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise MediaError("FFprobe could not inspect the input media.") from exc
    if not isinstance(metadata, dict) or not isinstance(metadata.get("streams"), list):
        raise MediaError("FFprobe returned an invalid media description.")
    return metadata


def assemble_video(
    clips: Sequence[str | Path],
    output_path: str | Path,
    *,
    profile: ExportProfile = "vertical",
    fps: int = 30,
    timeout_seconds: int = 900,
    trim_ranges: Sequence[tuple[float, float | None] | None] | None = None,
) -> Path:
    """Normalize and concatenate local video clips into a silent H.264 MP4.

    Each clip is scaled to fit the selected canvas, padded without cropping,
    assigned square pixels and a common frame rate, then concatenated.
    The function never downloads media or invokes a shell.
    """
    if profile not in PROFILES:
        raise MediaError("Unsupported export profile.")
    if not 1 <= len(clips) <= 50:
        raise MediaError("Provide between 1 and 50 video clips.")
    if not 1 <= fps <= 60:
        raise MediaError("Frame rate must be between 1 and 60 FPS.")

    sources = [Path(item).expanduser().resolve() for item in clips]
    for source in sources:
        if not source.is_file():
            raise MediaError(f"Input media file does not exist: {source.name}")
        if source.stat().st_size == 0:
            raise MediaError(f"Input media file is empty: {source.name}")

    destination = Path(output_path).expanduser().resolve()
    if destination.suffix.lower() != ".mp4":
        raise MediaError("Output filename must use the .mp4 extension.")
    if destination in sources:
        raise MediaError("Output file must not overwrite an input clip.")
    if not destination.parent.is_dir():
        raise MediaError("Output directory does not exist.")

    if trim_ranges is not None and len(trim_ranges) != len(sources):
        raise MediaError("Provide one trim range for each clip.")
    normalized_trims = list(trim_ranges) if trim_ranges is not None else [None] * len(sources)
    for trim in normalized_trims:
        if trim is None:
            continue
        start, end = trim
        if not math.isfinite(start) or start < 0:
            raise MediaError("Clip start time must be a finite non-negative number.")
        if end is not None and (not math.isfinite(end) or end <= start):
            raise MediaError("Clip end time must be greater than its start time.")

    width, height = PROFILES[profile]
    command = [_executable("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y"]
    for source, trim in zip(sources, normalized_trims):
        if trim is not None:
            start, end = trim
            if start > 0:
                command.extend(["-ss", f"{start:.3f}"])
            if end is not None:
                command.extend(["-t", f"{end - start:.3f}"])
        command.extend(["-i", str(source)])

    filters = []
    labels = []
    for index in range(len(sources)):
        label = f"v{index}"
        filters.append(
            f"[{index}:v:0]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},"
            f"format=yuv420p[{label}]"
        )
        labels.append(f"[{label}]")
    filters.append(
        "".join(labels) + f"concat=n={len(sources)}:v=1:a=0[vout]"
    )
    command.extend([
        "-filter_complex", ";".join(filters),
        "-map", "[vout]",
        "-an",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-movflags", "+faststart",
        str(destination),
    ])

    try:
        subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=timeout_seconds
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaError("Video export exceeded its time limit.") from exc
    except subprocess.CalledProcessError as exc:
        # Do not echo arbitrary provider paths or complete FFmpeg diagnostics to API clients.
        raise MediaError("FFmpeg could not assemble the supplied clips.") from exc

    if not destination.is_file() or destination.stat().st_size == 0:
        raise MediaError("FFmpeg finished without producing a valid output file.")
    return destination
