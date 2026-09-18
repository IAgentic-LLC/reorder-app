"""Chapter 7, orchestration tier: the pause/resume endpoints' own
request/response contract. `InMemorySaver` stands in for the real
Postgres checkpointer, same reasoning Book 2's own approval-workflow
tests used: the mechanism under test here is the API shape, not
durability, tests/integration covers a real Postgres connection.
"""

from langgraph.checkpoint.memory import InMemorySaver
from fastapi.testclient import TestClient

from reliable_agents_labs.models import ModelResult
from reliable_agents_labs.reorder_workflow import build_approval_workflow
from reorder_app.api import app
from reorder_app.auth import Principal, verify_token
from tests.fakes import ScriptedModelClient


def _text_result(text: str) -> ModelResult:
    return ModelResult(
        text=text, input_tokens=10, output_tokens=5, model_id="scripted", provider="scripted"
    )


def _bypass_auth():
    app.dependency_overrides[verify_token] = lambda: Principal(subject="test|bypassed")


def test_a_reorder_proposal_returns_pending_approval_and_a_thread_id():
    model = ScriptedModelClient(
        [_text_result("SKU-1029 is low, reorder it."), _text_result('{"reorder": true}')]
    )
    app.state.reorder_graph = build_approval_workflow(
        model_client=model, checkpointer=InMemorySaver()
    )
    _bypass_auth()
    try:
        client = TestClient(app)
        response = client.post("/v1/reorder-requests", json={"question": "restock SKU-1029?"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["pending_approval"] is True
    assert body["answer"] is None
    assert body["thread_id"]


def test_approving_a_pending_request_logs_it():
    model = ScriptedModelClient(
        [_text_result("SKU-1029 is low, reorder it."), _text_result('{"reorder": true}')]
    )
    app.state.reorder_graph = build_approval_workflow(
        model_client=model, checkpointer=InMemorySaver()
    )
    _bypass_auth()
    try:
        client = TestClient(app)
        started = client.post("/v1/reorder-requests", json={"question": "restock SKU-1029?"})
        thread_id = started.json()["thread_id"]

        response = client.post(
            f"/v1/reorder-requests/{thread_id}/decision",
            json={"approved": True, "note": "go ahead"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["logged"] is True
    assert body["note"] == "go ahead"


def test_a_question_that_needs_no_reorder_completes_without_pausing():
    model = ScriptedModelClient(
        [
            _text_result("SKU-2040 is well stocked, no action needed."),
            _text_result('{"reorder": false}'),
        ]
    )
    app.state.reorder_graph = build_approval_workflow(
        model_client=model, checkpointer=InMemorySaver()
    )
    _bypass_auth()
    try:
        client = TestClient(app)
        response = client.post("/v1/reorder-requests", json={"question": "restock SKU-2040?"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["pending_approval"] is False
    assert body["answer"] is not None
