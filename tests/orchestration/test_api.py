"""Chapter 5: verifies the API's request/response contract, not the
agent's tool-calling logic (Book 2 already covers that). A single
scripted, no-tool-call answer is enough here; re-testing tool-calling
would just duplicate reliable-agents-labs' own chapter 6 tests for no
new reason.
"""

from fastapi.testclient import TestClient
from reliable_agents_labs.models import ModelResult

from reorder_app.api import app, get_model_client
from reorder_app.auth import Principal, verify_token
from tests.fakes import ScriptedModelClient


def _bypass_auth():
    """Chapter 5's tests are about the API contract, not chapter 6's
    identity check. Overriding verify_token keeps them testing exactly
    what they said they test, chapter 6's own tests exercise this
    dependency for real.
    """
    app.dependency_overrides[verify_token] = lambda: Principal(subject="test|bypassed")


def test_ask_question_returns_grounded_answer():
    scripted = ScriptedModelClient(
        [
            ModelResult(
                text="We currently have 4 units of SKU-1029 in stock.",
                input_tokens=12,
                output_tokens=11,
                model_id="fake",
                provider="fake",
            )
        ]
    )
    app.dependency_overrides[get_model_client] = lambda: scripted
    _bypass_auth()
    try:
        client = TestClient(app)
        response = client.post(
            "/v1/questions", json={"question": "How many units of SKU-1029 do we have?"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"answer": "We currently have 4 units of SKU-1029 in stock."}


def test_upstream_model_failure_returns_typed_error_shape():
    class BrokenClient:
        async def generate(self, **kwargs):
            raise RuntimeError("simulated provider outage")

    app.dependency_overrides[get_model_client] = lambda: BrokenClient()
    _bypass_auth()
    try:
        client = TestClient(app)
        response = client.post("/v1/questions", json={"question": "anything"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    body = response.json()
    assert body["type"] == "https://reorder-app.dev/problems/upstream-model-error"
    assert body["status"] == 502
    assert "simulated provider outage" in body["detail"]


def test_malformed_request_returns_422_not_a_raw_traceback():
    _bypass_auth()
    try:
        client = TestClient(app)
        response = client.post("/v1/questions", json={"not_a_question": "oops"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
