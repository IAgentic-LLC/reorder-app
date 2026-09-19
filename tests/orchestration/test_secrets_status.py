"""Chapter 26, orchestration tier: the real HTTP surface for the
secret-status endpoint, real JWT verification bypassed the same way
chapter 5's own test_api.py already does, since this test is about the
route's own contract, not identity.
"""

from fastapi.testclient import TestClient
from reorder_app.api import app
from reorder_app.auth import Principal, verify_token


def test_secret_status_never_returns_a_real_secret_value(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "a-very-recognizable-secret-value")
    app.dependency_overrides[verify_token] = lambda: Principal(subject="test|bypassed")
    try:
        client = TestClient(app)
        response = client.get("/v1/ops/secret-status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert "a-very-recognizable-secret-value" not in response.text
    assert "process_started_at" in body
    assert len(body["secret_digest"]) == 12


def test_secret_status_requires_a_real_bearer_token():
    client = TestClient(app)
    response = client.get("/v1/ops/secret-status")

    assert response.status_code in (401, 403)
