"""Chapter 6, contract tier: a real, controlled call to the actual live
Auth0 tenant, fetching a real token via the client-credentials flow and
verifying this API accepts it for real. Requires AUTH0_DOMAIN,
AUTH0_AUDIENCE, AUTH0_TEST_CLIENT_ID, AUTH0_TEST_CLIENT_SECRET in the
environment (see .env), skipped otherwise rather than failing CI runs
that don't have a tenant configured.
"""

import os

import httpx
import pytest
from fastapi.testclient import TestClient
from reorder_app.api import app, get_model_client

from tests.fakes import ScriptedModelClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("AUTH0_TEST_CLIENT_SECRET"),
    reason="No live Auth0 tenant configured for this environment",
)


def test_real_token_from_live_tenant_is_accepted():
    token_response = httpx.post(
        f"https://{os.environ['AUTH0_DOMAIN']}/oauth/token",
        json={
            "client_id": os.environ["AUTH0_TEST_CLIENT_ID"],
            "client_secret": os.environ["AUTH0_TEST_CLIENT_SECRET"],
            "audience": os.environ["AUTH0_AUDIENCE"],
            "grant_type": "client_credentials",
        },
        timeout=10,
    )
    token_response.raise_for_status()
    access_token = token_response.json()["access_token"]

    from reliable_agents_labs.models import ModelResult

    scripted = ScriptedModelClient(
        [
            ModelResult(
                text="We currently have 4 units of SKU-1029 in stock.",
                input_tokens=1,
                output_tokens=1,
                model_id="fake",
                provider="fake",
            )
        ]
    )
    app.dependency_overrides[get_model_client] = lambda: scripted
    try:
        client = TestClient(app)
        response = client.post(
            "/v1/questions",
            json={"question": "How many units of SKU-1029 do we have?"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
