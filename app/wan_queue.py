"""Gradio queue client for the configured Wan 2.2 image-to-video Space."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import HTTPException

from .config import settings

_ALLOWED_HOST = "zerogpu-aoti-wan2-2-fp8da-aoti-faster.hf.space"


def _base_url() -> str:
    parsed = urlparse(settings.wan_base_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != _ALLOWED_HOST
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(500, "Wan provider URL is not an approved HTTPS origin.")
    return f"https://{_ALLOWED_HOST}"


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if settings.hf_token:
        headers["Authorization"] = f"Bearer {settings.hf_token}"
    return headers


def _file_data(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if isinstance(value.get("url"), str) or isinstance(value.get("path"), str):
            found.append(value)
        for child in value.values():
            found.extend(_file_data(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_file_data(child))
    return found


async def generate_wan_from_local_image(
    image_path: Path,
    *,
    prompt: str,
    negative_prompt: str = "",
    duration_seconds: float = 2.0,
    steps: int = 4,
    guidance_scale: float = 1.0,
    guidance_scale_2: float = 1.0,
    seed: int = 42,
    randomize_seed: bool = True,
) -> dict[str, Any]:
    """Upload a local image to Gradio, queue generation, and return video FileData."""
    if not image_path.is_file():
        raise HTTPException(404, "The selected scene image is missing from local storage.")
    base = _base_url()
    timeout = httpx.Timeout(connect=20, read=max(settings.generation_wait_seconds, 300), write=60, pool=20)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, headers=_headers()) as client:
            with image_path.open("rb") as image_file:
                uploaded = await client.post(
                    f"{base}/gradio_api/upload",
                    files={"files": (image_path.name, image_file, "application/octet-stream")},
                )
            uploaded.raise_for_status()
            upload_data = uploaded.json()
            if not isinstance(upload_data, list) or not upload_data or not isinstance(upload_data[0], str):
                raise HTTPException(502, "Wan image upload returned an unexpected response.")
            file_data = {
                "path": upload_data[0],
                "orig_name": image_path.name,
                "meta": {"_type": "gradio.FileData"},
            }
            submitted = await client.post(
                f"{base}/gradio_api/call/v2/generate_video",
                json={
                    "input_image": file_data,
                    "prompt": prompt,
                    "steps": steps,
                    "negative_prompt": negative_prompt,
                    "duration_seconds": duration_seconds,
                    "guidance_scale": guidance_scale,
                    "guidance_scale_2": guidance_scale_2,
                    "seed": seed,
                    "randomize_seed": randomize_seed,
                },
            )
            submitted.raise_for_status()
            body = submitted.json()
            event_id = body.get("event_id") if isinstance(body, dict) else None
            if not isinstance(event_id, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,200}", event_id):
                raise HTTPException(502, "Wan did not return a valid generation event ID.")

            events: list[dict[str, Any]] = []
            current_event = "message"
            current_data: list[str] = []

            def flush() -> None:
                nonlocal current_event, current_data
                if current_data:
                    raw = "\\n".join(current_data)
                    try:
                        parsed: Any = json.loads(raw)
                    except json.JSONDecodeError:
                        parsed = raw
                    events.append({"event": current_event, "data": parsed})
                current_event, current_data = "message", []

            async with client.stream("GET", f"{base}/gradio_api/call/generate_video/{event_id}") as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("event:"):
                        current_event = line[6:].strip()
                    elif line.startswith("data:"):
                        current_data.append(line[5:].strip())
                    elif line == "":
                        flush()
                        if events and events[-1]["event"] in {"complete", "error"}:
                            break
                flush()
    except HTTPException:
        raise
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "Wan generation timed out. Check the provider Space before retrying.") from exc
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise HTTPException(502, f"Wan image-to-video request failed: {type(exc).__name__}") from exc

    if any(item["event"] == "error" for item in events):
        raise HTTPException(502, "Wan reported an image-to-video generation error.")
    completed = [item for item in events if item["event"] == "complete"]
    if not completed:
        raise HTTPException(504, "Wan did not complete the video before the wait limit.")
    files: list[dict[str, Any]] = []
    for item in completed:
        files.extend(_file_data(item.get("data")))
    video_file = next((item for item in files if isinstance(item.get("url"), str) and item["url"].startswith("https://")), None)
    if not video_file:
        raise HTTPException(502, "Wan completed but did not return a downloadable video URL.")
    return {"file": video_file, "events": events, "url": urljoin(base + "/", video_file["url"])}
