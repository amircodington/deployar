from fastapi.testclient import TestClient

from hamkar.main import app


def test_health() -> None:
    assert TestClient(app).get("/api/health").json() == {"ok": True}
