from fastapi.testclient import TestClient
from simple_fastapi_app.main import app

# run `python -m pytest` to test
def test_health():
    client = TestClient(app)

    response = client.get("/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}