"""Chapter 35, orchestration tier: `/v1/questions` and `/v1/usage` must
agree, through the real HTTP surface, on what a real request actually
cost. Overriding `get_model_client` with one shared
`CostTrackingModelClient` instance (not two separate ones) is what
makes that provable: production wires the exact same singleton into
both endpoints via `app.state.cost_tracker`.
"""

from fastapi.testclient import TestClient
from reliable_agents_labs.models import ModelResult
from reorder_app.api import app, get_model_client
from reorder_app.auth import Principal, verify_token
from reorder_app.cost import CostTrackingModelClient

from tests.fakes import ScriptedModelClient


def _bypass_auth():
    app.dependency_overrides[verify_token] = lambda: Principal(subject="test|bypassed")


def test_usage_reflects_real_cost_from_a_real_request():
    scripted = ScriptedModelClient(
        [
            ModelResult(
                text="4 units in stock.",
                input_tokens=1_000_000,
                output_tokens=0,
                model_id="fake",
                provider="fake",
            )
        ]
    )
    tracker = CostTrackingModelClient(scripted)
    app.dependency_overrides[get_model_client] = lambda: tracker
    _bypass_auth()
    try:
        client = TestClient(app)
        client.post("/v1/questions", json={"question": "How many units of SKU-1029?"})
        usage = client.get("/v1/usage")
    finally:
        app.dependency_overrides.clear()

    assert usage.status_code == 200
    body = usage.json()
    assert body["call_count"] == 1
    assert round(body["total_cost_usd"], 6) == 0.75


def test_usage_is_zero_before_any_real_request():
    tracker = CostTrackingModelClient(ScriptedModelClient([]))
    app.dependency_overrides[get_model_client] = lambda: tracker
    _bypass_auth()
    try:
        client = TestClient(app)
        usage = client.get("/v1/usage")
    finally:
        app.dependency_overrides.clear()

    assert usage.json() == {"total_cost_usd": 0.0, "call_count": 0}
