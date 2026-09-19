"""Chapter 32: pure summary logic, separated from the network code that
produces the raw results, so it can be unit-tested without a real
server, a real model, or a real network call.
"""

import statistics
from dataclasses import dataclass


@dataclass
class LoadResult:
    status: int | str
    elapsed_seconds: float
    question: str
    error: str | None = None


@dataclass
class LoadSummary:
    total: int
    successes: int
    failures: int
    p50_seconds: float
    p95_seconds: float
    min_seconds: float
    max_seconds: float


def summarize(results: list[LoadResult]) -> LoadSummary:
    if not results:
        raise ValueError("summarize() needs at least one result")

    latencies = sorted(r.elapsed_seconds for r in results)
    successes = [r for r in results if r.status == 200]
    p95_index = min(int(len(latencies) * 0.95), len(latencies) - 1)

    return LoadSummary(
        total=len(results),
        successes=len(successes),
        failures=len(results) - len(successes),
        p50_seconds=statistics.median(latencies),
        p95_seconds=latencies[p95_index],
        min_seconds=latencies[0],
        max_seconds=latencies[-1],
    )
