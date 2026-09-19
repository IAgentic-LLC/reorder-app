"""Chapter 35, unit tier: `CostTrackingModelClient` on its own, no
FastAPI, no real network call. Proves it passes a real `ModelResult`
through unchanged while accumulating a real dollar total, the same
claim chapter 34's `RetryingModelClient` tests proved for retries
instead of cost.
"""

from reliable_agents_labs.models import ModelResult
from reorder_app.cost import CostTrackingModelClient

from tests.fakes import ScriptedModelClient


def _text_result(text: str, input_tokens: int, output_tokens: int) -> ModelResult:
    return ModelResult(
        text=text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model_id="scripted",
        provider="scripted",
    )


async def test_it_passes_the_real_result_through_unchanged():
    scripted = ScriptedModelClient([_text_result("in stock", 100, 50)])
    tracker = CostTrackingModelClient(scripted)

    result = await tracker.generate(system="s", user="u")

    assert result.text == "in stock"


async def test_it_accumulates_real_cost_across_multiple_calls():
    scripted = ScriptedModelClient(
        [_text_result("first", 1_000_000, 0), _text_result("second", 0, 1_000_000)]
    )
    tracker = CostTrackingModelClient(scripted)

    await tracker.generate(system="s", user="u")
    await tracker.generate(system="s", user="u")

    # $0.75/million input tokens + $3.75/million output tokens, one
    # call of each, the real chapter-31 pricing this book has used
    # since Book 2, not a number invented for this test.
    assert tracker.call_count == 2
    assert round(tracker.total_cost_usd, 6) == round(0.75 + 3.75, 6)
