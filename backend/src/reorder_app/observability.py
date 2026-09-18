"""Chapter 16: Book 2's own chapter 9 already built real Langfuse
tracing for this exact agent, `ask_reorder_agent_traced`, and chapter
28 built it for the durable workflow, `run_reorder_workflow_traced`.
Both have sat unused since chapter 5, `reorder_app.api` calls the
untraced functions directly, a real, live-confirmed gap: real
`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` have been sitting in this
app's own `.env` since chapter 9's own scaffold, never once reaching
a real trace.

Two thin wrappers, not a rewrite: each nests inside Book 2's own
already-traced call (a real nested span, not a competing one) purely
to attach one thing Book 2's own single-caller code never needed, a
tag naming which real product a trace came from, `reorder-app`, now
that its traces share one Langfuse project with `pkgintel-app`'s own.

`get_client().update_current_trace(tags=...)` was the first thing
tried here, and a real `AttributeError` from actually running the
orchestration tests, not a hypothetical, caught that this Langfuse
version has no such method at all. `propagate_attributes`, a
module-level context manager, not a client method, is the real,
current way to set trace-level `tags` (also `user_id`, `session_id`),
entered as early as possible inside the already-`@observe`d span.
"""

from langfuse import observe, propagate_attributes
from reliable_agents_labs.models import ModelClient
from reliable_agents_labs.observability import ask_reorder_agent_traced, run_reorder_workflow_traced


@observe(name="reorder_app.ask_question")
async def ask_reorder_agent_tagged(question: str, client: ModelClient | None = None) -> str:
    with propagate_attributes(tags=["reorder-app"]):
        return await ask_reorder_agent_traced(question, client=client)


@observe(name="reorder_app.reorder_workflow")
async def run_reorder_workflow_tagged(graph, initial_state, config: dict) -> dict:
    with propagate_attributes(tags=["reorder-app"]):
        return await run_reorder_workflow_traced(graph, initial_state, config)
