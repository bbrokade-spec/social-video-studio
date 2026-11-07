from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_does_not_call_generation():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["generation_called"] is False


def test_provider_metadata_is_available():
    response = client.get("/api/v1/providers")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["providers"]}
    assert ids == {"z-image-turbo", "wan-2.2"}


def test_generation_is_disabled_without_server_api_key(monkeypatch):
    from app import main

    monkeypatch.setattr(main.settings, "allow_unauthenticated_generation", False)
    monkeypatch.setattr(main.settings, "api_key", "")
    response = client.post("/api/v1/images", json={"prompt": "test prompt"})
    assert response.status_code == 503


def test_openapi_declares_api_key_security():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["components"]["securitySchemes"]["ApiKeyAuth"]["name"] == "X-API-Key"
    operation = schema["paths"]["/api/v1/pipelines/image-to-video"]["post"]
    assert operation["security"] == [{"ApiKeyAuth": []}]
