"""Chapter 6: deterministic JWT verification tests. A local RSA keypair
stands in for Auth0's own signing key, exactly what a live JWKS endpoint
would hand back, without a real network call or a real Auth0 tenant on
every test run. `tests/contract/test_auth_live.py` is where the real
tenant gets exercised, this tier is about the verification logic itself.
"""

import time

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from reorder_app import auth
from reorder_app.api import app, get_model_client

from tests.fakes import ScriptedModelClient

_TEST_AUDIENCE = "https://reorder-app.dev/api"
_TEST_ISSUER = "https://test-tenant.auth0.com/"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _FakeSigningKey:
    def __init__(self, key):
        self.key = key


class _FakeJWKSClient:
    def get_signing_key_from_jwt(self, token: str) -> _FakeSigningKey:
        return _FakeSigningKey(_private_key.public_key())


def _make_token(
    *, audience=_TEST_AUDIENCE, issuer=_TEST_ISSUER, exp_delta=3600, subject="test|123"
):
    now = int(time.time())
    payload = {"sub": subject, "aud": audience, "iss": issuer, "iat": now, "exp": now + exp_delta}
    return jwt.encode(payload, _private_key, algorithm="RS256")


def _override_jwks(monkeypatch):
    monkeypatch.setattr(auth, "_jwks_client", _FakeJWKSClient())
    monkeypatch.setenv("AUTH0_AUDIENCE", _TEST_AUDIENCE)
    monkeypatch.setenv("AUTH0_DOMAIN", "test-tenant.auth0.com")


def _client_with_scripted_model():
    scripted = ScriptedModelClient(
        [
            __import__("reliable_agents_labs.models", fromlist=["ModelResult"]).ModelResult(
                text="We currently have 4 units of SKU-1029 in stock.",
                input_tokens=1,
                output_tokens=1,
                model_id="fake",
                provider="fake",
            )
        ]
    )
    app.dependency_overrides[get_model_client] = lambda: scripted
    return TestClient(app)


def test_missing_token_is_rejected(monkeypatch):
    _override_jwks(monkeypatch)
    client = _client_with_scripted_model()
    try:
        response = client.post("/v1/questions", json={"question": "anything"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code in (401, 403)
    body = response.json()
    assert body["status"] in (401, 403)


def test_valid_token_is_accepted(monkeypatch):
    _override_jwks(monkeypatch)
    client = _client_with_scripted_model()
    token = _make_token()
    try:
        response = client.post(
            "/v1/questions",
            json={"question": "How many units of SKU-1029 do we have?"},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"answer": "We currently have 4 units of SKU-1029 in stock."}


def test_expired_token_is_rejected(monkeypatch):
    _override_jwks(monkeypatch)
    client = _client_with_scripted_model()
    token = _make_token(exp_delta=-3600)
    try:
        response = client.post(
            "/v1/questions",
            json={"question": "anything"},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    body = response.json()
    assert body["type"] == "https://reorder-app.dev/problems/unauthorized"


def test_wrong_audience_is_rejected(monkeypatch):
    _override_jwks(monkeypatch)
    client = _client_with_scripted_model()
    token = _make_token(audience="https://someone-elses-api.dev")
    try:
        response = client.post(
            "/v1/questions",
            json={"question": "anything"},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
