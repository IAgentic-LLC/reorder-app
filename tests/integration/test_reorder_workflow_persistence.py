"""Chapter 7, integration tier: real persistence, a real local Postgres
(see compose.yaml), scripted model so the point under test (does the
state actually survive a fresh connection) is the only thing that can
fail. This is chapter 4's own promise, kept for real: two separate
checkpointer connections, standing in for two separate processes, both
reading and writing the same shared state, no module-level dict
anywhere.
"""

import os

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command

from reliable_agents_labs.models import ModelResult
from reliable_agents_labs.reorder_workflow import build_approval_workflow
from tests.fakes import ScriptedModelClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="No local Postgres configured for this environment, see compose.yaml",
)


def _text_result(text: str) -> ModelResult:
    return ModelResult(
        text=text, input_tokens=10, output_tokens=5, model_id="scripted", provider="scripted"
    )


async def test_a_paused_run_resumes_from_a_completely_fresh_connection():
    config = {"configurable": {"thread_id": "persistence-test-sku-1029"}}
    empty_state = {
        "question": "restock SKU-1029?",
        "answer": "",
        "reorder": False,
        "approved": False,
        "note": "",
        "logged": False,
    }

    # Process A: starts the run, pauses at await_approval, then this
    # connection closes entirely, nothing about this run lives in this
    # process's memory anymore.
    async with AsyncPostgresSaver.from_conn_string(os.environ["DATABASE_URL"]) as saver:
        await saver.setup()
        model = ScriptedModelClient(
            [_text_result("SKU-1029 is low, reorder it."), _text_result('{"reorder": true}')]
        )
        graph = build_approval_workflow(model_client=model, checkpointer=saver)
        paused = await graph.ainvoke(empty_state, config)
        assert "__interrupt__" in paused

    # Process B: a brand new connection and a brand new compiled graph,
    # standing in for a fresh server process that never ran this agent
    # at all. It resumes the exact same thread_id anyway.
    async with AsyncPostgresSaver.from_conn_string(os.environ["DATABASE_URL"]) as saver:
        graph = build_approval_workflow(model_client=ScriptedModelClient([]), checkpointer=saver)
        result = await graph.ainvoke(
            Command(resume={"approved": True, "note": "approved from a fresh connection"}),
            config,
        )

    assert result["logged"] is True
    assert result["note"] == "approved from a fresh connection"
