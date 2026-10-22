from fastapi.testclient import TestClient

from pulse.main import app


def test_health_reports_emulator_mode_by_default() -> None:
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json()["crm"] == "emulator"
