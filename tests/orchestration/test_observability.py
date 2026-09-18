"""Chapter 16, orchestration tier: the tagged wrappers' own tests, same
guarantee as Book 2's own `test_observability.py`/
`test_workflow_observability.py`: whether a trace also reaches
Langfuse depends on `LANGFUSE_PUBLIC_KEY` being set, but either way
these calls are harmless, scripted models throughout, never a real
network call to a model provider.
"""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from reliable_agents_labs.models import ModelResult
from reliable_agents_labs.reorder_workflow import build_approval_workflow
from reorder_app.observability import ask_reorder_agent_tagged, run_reorder_workflow_tagged

from tests.fakes import ScriptedModelClient

_EMPTY_STATE = {
    "question": "restock SKU-1029?",
    "answer": "",
    "reorder": False,
    "approved": False,
    "note": "",
    "logged": False,
}


def _text_result(text: str) -> ModelResult:
    return ModelResult(
        text=text, input_tokens=10, output_tokens=5, model_id="scripted", provider="scripted"
    )


async def test_the_tagged_question_wrapper_returns_the_same_answer():
    model = ScriptedModelClient(
        [_text_result("We currently have 4 units of SKU-1029 in stock.")]
    )
    answer = await ask_reorder_agent_tagged("How many units of SKU-1029 do we have?", client=model)
    assert answer == "We currently have 4 units of SKU-1029 in stock."


async def test_the_tagged_workflow_wrapper_returns_the_same_result():
    model = ScriptedModelClient(
        [_text_result("SKU-1029 is fine."), _text_result('{"reorder": false}')]
    )
    graph = build_approval_workflow(model_client=model, checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "tagged-test-1"}}

    result = await run_reorder_workflow_tagged(graph, _EMPTY_STATE, config)

    assert result["reorder"] is False


async def test_a_tagged_resume_call_does_not_crash_either():
    model = ScriptedModelClient(
        [_text_result("SKU-1029 is low, reorder it."), _text_result('{"reorder": true}')]
    )
    graph = build_approval_workflow(model_client=model, checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "tagged-test-2"}}
    await run_reorder_workflow_tagged(graph, _EMPTY_STATE, config)

    resumed = await run_reorder_workflow_tagged(
        graph, Command(resume={"approved": True, "note": "ok"}), config
    )

    assert resumed["logged"] is True
