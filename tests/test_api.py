"""API smoke tests."""

from fastapi.testclient import TestClient

from shpoet.api.main import app


client = TestClient(app)


def test_health_check() -> None:
    """Ensure the health endpoint returns an OK payload."""

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
