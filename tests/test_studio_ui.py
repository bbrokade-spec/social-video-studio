from fastapi.testclient import TestClient

from app.main import app


def test_local_studio_home_serves_interface_without_authentication():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "Social Video Studio" in response.text
    assert 'id="apiKey"' in response.text
    assert "sessionStorage" not in response.text
    assert "localStorage" not in response.text


def test_studio_interface_is_same_origin_api_client():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert 'fetch("/api/v1/projects"' in response.text
    assert 'X-API-Key' in response.text
