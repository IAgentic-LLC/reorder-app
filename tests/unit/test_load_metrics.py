"""Chapter 32: pure summary logic, no network, no real load test
needed to prove this part works.
"""

import pytest
from reorder_app.load_metrics import LoadResult, summarize


def test_summarize_reports_real_percentiles_and_success_counts():
    results = [
        LoadResult(status=200, elapsed_seconds=0.5, question="a"),
        LoadResult(status=200, elapsed_seconds=1.0, question="b"),
        LoadResult(status=200, elapsed_seconds=1.5, question="c"),
        LoadResult(status=500, elapsed_seconds=2.0, question="d"),
    ]

    summary = summarize(results)

    assert summary.total == 4
    assert summary.successes == 3
    assert summary.failures == 1
    assert summary.p50_seconds == 1.25
    assert summary.min_seconds == 0.5
    assert summary.max_seconds == 2.0


def test_summarize_treats_connection_errors_as_failures():
    results = [
        LoadResult(status=200, elapsed_seconds=0.5, question="a"),
        LoadResult(status="error", elapsed_seconds=30.0, question="b", error="timeout"),
    ]

    summary = summarize(results)

    assert summary.successes == 1
    assert summary.failures == 1


def test_summarize_refuses_an_empty_result_list():
    with pytest.raises(ValueError):
        summarize([])
