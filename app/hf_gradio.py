import json
import re
from typing import Any, AsyncIterator
from urllib.parse import urljoin

import httpx
from fastapi import HTTPException

from .config import settings


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if settings.hf_token:
        headers["Authorization"] = f"Bearer {settings.hf_token}"
    return headers


def _safe_base(url: str) -> str:
    if not url.startswith("https://"):
        raise HTTPException(500, "Provider URL must use HTTPS")
    return url.rstrip("/")


async def submit_zimage(payload: dict[str, Any]) -> str:
    base = _safe_base(settings.zimage_base_url)
    url = f"{base}/gradio_api/call/v2/generate"
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=_headers())
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Z-Image request failed: {type(exc).__name__}") from exc
    event_id = body.get("event_id") if isinstance(body, dict) else None
    if not event_id:
        raise HTTPException(502, f"Z-Image did not return an event_id: {body}")
    return str(event_id)


async def get_zimage_events(event_id: str) -> list[str]:
    base = _safe_base(settings.zimage_base_url)
    url = f"{base}/gradio_api/call/generate/{event_id}"
    events: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=None, headers=_headers()) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        events.append(line[5:].strip())
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Z-Image result retrieval failed: {type(exc).__name__}") from exc
    return events


async def submit_wan(payload: dict[str, Any]) -> str:
    base = _safe_base(settings.wan_base_url)
    url = f"{base}/run/generate_video"
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=_headers())
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Wan request failed: {type(exc).__name__}") from exc
    event_id = body.get("event_id") if isinstance(body, dict) else None
    if not event_id:
        # Some Gradio legacy endpoints return a direct result rather than an event id.
        if isinstance(body, dict) and "data" in body:
            return json.dumps({"direct_result": body["data"]})
        raise HTTPException(502, f"Wan did not return an event_id: {body}")
    return str(event_id)


async def get_wan_result(event_id: str) -> dict[str, Any]:
    base = _safe_base(settings.wan_base_url)
    url = f"{base}/queue/data?session_hash={event_id}"
    # This provisional adapter does not assume queue session IDs equal event IDs.
    # The exact OpenAPI result schema must be validated before production use.
    raise HTTPException(
        501,
        "Wan result retrieval is not yet implemented. Confirm the Space's queue/SSE response contract before enabling production calls.",
    )


def output_urls(events: list[str]) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for item in events:
        if not item or item in ("null", "[DONE]"):
            continue
        try:
            parsed = json.loads(item)
        except json.JSONDecodeError:
            outputs.append({"raw": item})
            continue
        # Keep the provider response intact. Gradio FileData objects can be nested.
        outputs.append({"data": parsed})
    return outputs
