"""Shared test fakes. Not a test file itself, imported by orchestration
tests across every chapter. `ScriptedModelClient` is copied from
`reliable-agents-labs`' own `tests/fakes.py` rather than imported, since
test doubles live under `tests/` there and are not part of the installed
package. This is a test-scaffolding duplication, not a rewrite of the
agent logic itself, which stays imported, not copied, see `api.py`.
"""

from reliable_agents_labs.models import ModelResult


class ScriptedModelClient:
    """A deterministic stand-in for any real ModelClient adapter. Feed it a
    list of canned ModelResults; each call to generate() returns the next
    one.
    """

    def __init__(self, scripted_results: list[ModelResult]) -> None:
        self._results = iter(scripted_results)

    async def generate(
        self,
        *,
        system: str,
        user: str,
        tools: list[dict] | None = None,
        history: list[dict] | None = None,
    ) -> ModelResult:
        return next(self._results)


class FakeJobQueue:
    """Chapter 9's orchestration-tier stand-in for the real SAQ queue.
    Records what got enqueued instead of touching a real Postgres
    connection, the same "swap the real thing for a double behind the
    same seam" pattern as `ScriptedModelClient`.
    """

    def __init__(self) -> None:
        self.enqueued: list[tuple[str, dict]] = []

    async def enqueue(self, function_name: str, **kwargs) -> object:
        self.enqueued.append((function_name, kwargs))
        return object()
