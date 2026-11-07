import ipaddress
import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from .config import settings


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if settings.hf_token:
        headers["Authorization"] = f"Bearer {settings.hf_token}"
    return headers


def _safe_base(url: str, expected_host: str) -> str:
    """Validate a provider origin before attaching the Hugging Face bearer token."""
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.hostname.lower() != expected_host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise HTTPException(500, "Provider URL is not an approved HTTPS origin")
    return f"https://{expected_host}"


def _validate_public_image_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise HTTPException(422, "input_image must be a public HTTPS URL")
    host = parsed.hostname.lower()
    if host in {"localhost", "metadata.google.internal"} or host.endswith(".localhost"):
        raise HTTPException(422, "Private or local image hosts are not permitted")
    try:
        address = ipaddress.ip_address(host)
        if not address.is_global:
            raise HTTPException(422, "Private or non-public IP addresses are not permitted")
    except ValueError:
        pass
    return url


async def submit_zimage(payload: dict[str, Any]) -> str:
    base = _safe_base(settings.zimage_base_url, "mcp-tools-z-image-turbo.hf.space")
    url = f"{base}/gradio_api/call/v2/generate"
    timeout = httpx.Timeout(connect=20.0, read=settings.http_timeout_seconds, write=30.0, pool=20.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.post(url, json=payload, headers=_headers())
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Z-Image submission failed: {type(exc).__name__}") from exc

    event_id = body.get("event_id") if isinstance(body, dict) else None
    if not isinstance(event_id, str) or not event_id:
        raise HTTPException(502, "Z-Image did not return a valid event_id")
    return event_id


async def get_zimage_events(event_id: str) -> list[dict[str, Any]]:
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,200}", event_id):
        raise HTTPException(422, "Invalid Z-Image event_id")

    base = _safe_base(settings.zimage_base_url, "mcp-tools-z-image-turbo.hf.space")
    url = f"{base}/gradio_api/call/generate/{event_id}"
    timeout = httpx.Timeout(connect=20.0, read=settings.generation_wait_seconds, write=20.0, pool=20.0)
    collected: list[dict[str, Any]] = []
    current_event = "message"
    current_data: list[str] = []

    def flush_event() -> None:
        nonlocal current_event, current_data
        if current_data:
            raw = "\n".join(current_data)
            try:
                parsed: Any = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw
            collected.append({"event": current_event, "data": parsed})
        current_event = "message"
        current_data = []

    try:
        async with httpx.AsyncClient(timeout=timeout, headers=_headers(), follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("event:"):
                        current_event = line[6:].strip()
                    elif line.startswith("data:"):
                        current_data.append(line[5:].strip())
                    elif line == "":
                        flush_event()
                        if collected and collected[-1]["event"] in {"complete", "error"}:
                            break
                flush_event()
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Z-Image result retrieval failed: {type(exc).__name__}") from exc

    return collected


def _find_filedata(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if any(key in value for key in ("url", "path")) and (
            "orig_name" in value or "mime_type" in value or "size" in value or "path" in value
        ):
            found.append(value)
        for child in value.values():
            found.extend(_find_filedata(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_find_filedata(child))
    return found


async def generate_wan(payload: dict[str, Any]) -> dict[str, Any]:
    base = _safe_base(settings.wan_base_url, "zerogpu-aoti-wan2-2-fp8da-aoti-faster.hf.space")
    url = f"{base}/run/generate_video"
    timeout = httpx.Timeout(
        connect=20.0,
        read=max(settings.generation_wait_seconds, 300),
        write=60.0,
        pool=20.0,
    )
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.post(url, json=payload, headers=_headers())
            response.raise_for_status()
            body = response.json()
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "Wan generation timed out. Check the Space before retrying.") from exc
    except httpx.HTTPStatusError as exc:
        # Do not echo provider response bodies because they may contain internal details.
        raise HTTPException(502, f"Wan generation returned HTTP {exc.response.status_code}") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, f"Wan generation failed: {type(exc).__name__}") from exc

    if not isinstance(body, dict):
        raise HTTPException(502, "Wan returned an unexpected response format")
    output = body.get("output")
    if not isinstance(output, dict):
        raise HTTPException(502, "Wan response did not contain the expected FileData output")

    filedata = _find_filedata(output)
    return {"output": output, "filedata": filedata, "raw_response": body}
