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
