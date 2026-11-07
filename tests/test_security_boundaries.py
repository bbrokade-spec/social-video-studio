import pytest
from fastapi import HTTPException

from app.hf_gradio import _safe_base, _validate_public_image_url


def test_safe_base_accepts_exact_approved_https_origin():
    assert _safe_base(
        "https://mcp-tools-z-image-turbo.hf.space/",
        "mcp-tools-z-image-turbo.hf.space",
    ) == "https://mcp-tools-z-image-turbo.hf.space"


@pytest.mark.parametrize(
    "url",
    [
        "http://mcp-tools-z-image-turbo.hf.space",
        "https://attacker.example",
        "https://mcp-tools-z-image-turbo.hf.space.attacker.example",
        "https://user:password@mcp-tools-z-image-turbo.hf.space",
        "https://mcp-tools-z-image-turbo.hf.space:8443",
        "https://mcp-tools-z-image-turbo.hf.space/proxy",
        "https://mcp-tools-z-image-turbo.hf.space/?token=leak",
    ],
)
def test_safe_base_rejects_unapproved_provider_origins(url):
    with pytest.raises(HTTPException) as exc:
        _safe_base(url, "mcp-tools-z-image-turbo.hf.space")
    assert exc.value.status_code == 500


def test_public_image_url_requires_https_and_hostname():
    assert _validate_public_image_url("https://images.example.com/frame.png") == (
        "https://images.example.com/frame.png"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://images.example.com/frame.png",
        "file:///etc/passwd",
        "https://localhost/image.png",
        "https://127.0.0.1/image.png",
        "https://192.168.1.10/image.png",
        "https://metadata.google.internal/latest/meta-data",
    ],
)
def test_public_image_url_rejects_local_or_non_https_targets(url):
    with pytest.raises(HTTPException) as exc:
        _validate_public_image_url(url)
    assert exc.value.status_code == 422
