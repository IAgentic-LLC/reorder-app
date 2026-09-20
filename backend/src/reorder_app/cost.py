"""Chapter 35: `pkgintel-app` has tracked real per-request dollar cost
since chapter 15, using `reliable_agents_labs.cost.estimate_cost` on
every real `ModelResult`. `reorder-app` never has. Unlike `triage-app`'s
specialists, `ask_reorder_agent_with_tools` and the approval workflow's
own agent node are Book 2's own functions, and neither one exposes the
`on_result` hook chapter 31 of Book 2 added to `run_tool_loop`, so
there is no hook to pass here the way chapter 34 already found for
`triage-app`.

What every real `ModelClient` adapter shares instead is `generate()`
itself, the exact same shape `RetryingModelClient` (chapter 34) already
wraps, for a different reason. Wrapping it here, for cost instead of
retries, needs no change to Book 2's code at all: `build_approval_workflow`
has accepted any `ModelClient`-shaped object as its own `model_client`
argument since chapter 7, this is simply a different one.
"""

from reliable_agents_labs.cost import estimate_cost
from reliable_agents_labs.models import ModelClient, ModelResult


class CostTrackingModelClient:
    """Wraps a real client, records every real `ModelResult` that passes
    through it, and hands the result back unchanged. A single instance,
    shared across every request this process handles, is this product's
    only cost ledger, real but process-lifetime, not durable: a restart
    loses it, unlike `pkgintel-app`'s own Postgres-backed `tenant_usage`
    table. A disclosed, honest limitation, not a hidden one.
    """

    def __init__(self, client: ModelClient) -> None:
        self._client = client
        self.total_cost_usd = 0.0
        self.call_count = 0

    async def generate(
        self,
        *,
        system: str,
        user: str,
        tools: list[dict] | None = None,
        history: list[dict] | None = None,
    ) -> ModelResult:
        result = await self._client.generate(system=system, user=user, tools=tools, history=history)
        self.total_cost_usd += estimate_cost(result)
        self.call_count += 1
        return result
