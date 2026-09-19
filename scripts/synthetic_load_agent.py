"""Chapter 32: a synthetic load agent, not a static load-testing
script. It uses the real model once to generate a batch of realistic,
varied questions about this app's own real inventory, then fires them
concurrently at a real target, local or the live production
deployment, measuring real latency and real error rates under real
concurrent load, the same shape of load a real launch or a real
marketing push could actually produce.
"""

import argparse
import asyncio
import json
import os
import sys

import httpx
from dotenv import load_dotenv
from reliable_agents_labs.models import build_model_client

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from reorder_app.load_metrics import LoadResult, summarize  # noqa: E402

load_dotenv()

REAL_SKUS = ["SKU-1029", "SKU-2040", "SKU-3311"]

GENERATION_SYSTEM_PROMPT = (
    "You generate realistic customer support questions for a real "
    "inventory reorder assistant. Given a list of real SKUs, write the "
    "requested number of varied, natural-sounding questions a real "
    "person might ask about whether to reorder them. Vary phrasing, "
    "tone, and urgency. Respond with a JSON array of strings only, no "
    "markdown fences, no commentary."
)


async def generate_synthetic_questions(n: int) -> list[str]:
    client = build_model_client("answer_model")
    result = await client.generate(
        system=GENERATION_SYSTEM_PROMPT,
        user=f"Generate exactly {n} questions about these SKUs: {', '.join(REAL_SKUS)}",
    )
    text = result.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    return json.loads(text)


async def _fetch_token(auth0_domain: str, client_id: str, client_secret: str, audience: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://{auth0_domain}/oauth/token",
            json={
                "client_id": client_id,
                "client_secret": client_secret,
                "audience": audience,
                "grant_type": "client_credentials",
            },
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()["access_token"]


async def _fire_one(
    client: httpx.AsyncClient, base_url: str, token: str, question: str
) -> LoadResult:
    loop = asyncio.get_event_loop()
    start = loop.time()
    try:
        response = await client.post(
            f"{base_url}/v1/reorder-requests",
            json={"question": question},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        elapsed = loop.time() - start
        return LoadResult(status=response.status_code, elapsed_seconds=elapsed, question=question)
    except httpx.HTTPError as exc:
        elapsed = loop.time() - start
        return LoadResult(
            status="error", elapsed_seconds=elapsed, question=question, error=str(exc)
        )


async def run_load_test(base_url: str, token: str, questions: list[str]) -> list[LoadResult]:
    async with httpx.AsyncClient() as client:
        tasks = [_fire_one(client, base_url, token, q) for q in questions]
        return await asyncio.gather(*tasks)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--n", type=int, default=15)
    args = parser.parse_args()

    print(f"Generating {args.n} real, varied synthetic questions...")
    questions = await generate_synthetic_questions(args.n)
    print(f"Generated {len(questions)} questions.")

    token = await _fetch_token(
        os.environ["AUTH0_DOMAIN"],
        os.environ["AUTH0_TEST_CLIENT_ID"],
        os.environ["AUTH0_TEST_CLIENT_SECRET"],
        os.environ["AUTH0_AUDIENCE"],
    )

    print(f"Firing {len(questions)} requests concurrently at {args.base_url}...")
    results = await run_load_test(args.base_url, token, questions)

    summary = summarize(results)
    print(f"\nTotal requests: {summary.total}")
    print(f"Successful (200): {summary.successes}")
    print(f"Failed: {summary.failures}")
    print(f"p50 latency: {summary.p50_seconds:.2f}s")
    print(f"p95 latency: {summary.p95_seconds:.2f}s")
    print(f"min latency: {summary.min_seconds:.2f}s")
    print(f"max latency: {summary.max_seconds:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
