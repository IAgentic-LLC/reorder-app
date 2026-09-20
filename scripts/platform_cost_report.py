"""Chapter 35: a real, if incomplete, answer to "what did this whole
platform actually cost," not one product's own number. `reorder-app`
and `triage-app` each gained a real `/v1/usage` endpoint this chapter;
`pkgintel-app` has had one since chapter 15. This script is the first
thing in this book that ever asks all three the same question in one
place.

"Incomplete" is not a bug this script hides. Two real, already-disclosed
access-boundary gaps mean two of the three products can't actually be
queried unattended right now: `triage-app`'s own M2M client still has
no grant on its own API (chapter 22, still open per `docs/access-review.md`),
and `pkgintel-app`'s tenant identity requires a real user login, since
Auth0 Organizations excludes M2M entirely (chapter 14's own live
finding). A platform cost report that silently skipped those and only
showed `reorder-app`'s real number would be more misleading than useful;
this one names exactly which products it could and couldn't reach, and
why, every time it runs.
"""

import argparse
import asyncio

import httpx
from dotenv import dotenv_values

PRODUCTS = [
    {
        "name": "reorder-app",
        "env_file": "../reorder-app/.env",
        "default_base_url": "http://127.0.0.1:8000",
    },
    {
        "name": "triage-app",
        "env_file": "../triage-app/.env",
        "default_base_url": "http://127.0.0.1:8020",
    },
    {
        "name": "pkgintel-app",
        "env_file": "../pkgintel-app/.env",
        "default_base_url": "http://127.0.0.1:8010",
    },
]


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


def missing_credential_reason(env: dict) -> str | None:
    """Pure, no network: the exact same check `_usage_for` needs before
    it ever tries a real HTTP call, pulled out so it has a real unit
    test instead of only ever being exercised live.
    """
    required = (
        "AUTH0_TEST_CLIENT_ID",
        "AUTH0_TEST_CLIENT_SECRET",
        "AUTH0_DOMAIN",
        "AUTH0_AUDIENCE",
    )
    if all(env.get(key) for key in required):
        return None
    return "no M2M client credentials configured for this product"


async def _usage_for(product: dict, base_url: str) -> dict:
    env = dotenv_values(product["env_file"])
    reason = missing_credential_reason(env)
    if reason is not None:
        return {"product": product["name"], "reachable": False, "reason": reason}

    domain = env["AUTH0_DOMAIN"]
    audience = env["AUTH0_AUDIENCE"]
    client_id = env["AUTH0_TEST_CLIENT_ID"]
    client_secret = env["AUTH0_TEST_CLIENT_SECRET"]

    try:
        token = await _fetch_token(domain, client_id, client_secret, audience)
    except httpx.HTTPError as exc:
        return {
            "product": product["name"],
            "reachable": False,
            "reason": f"could not obtain a real token: {exc}",
        }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base_url}/v1/usage",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return {
            "product": product["name"],
            "reachable": False,
            "reason": f"a real token was issued but /v1/usage rejected it: {exc}",
        }

    body = response.json()
    return {
        "product": product["name"],
        "reachable": True,
        "total_cost_usd": body["total_cost_usd"],
    }


async def build_report(base_urls: dict[str, str]) -> list[dict]:
    return await asyncio.gather(
        *(_usage_for(product, base_urls[product["name"]]) for product in PRODUCTS)
    )


def _print_report(results: list[dict]) -> None:
    print("Platform cost report")
    print("=" * 40)
    platform_total = 0.0
    for result in results:
        if result["reachable"]:
            print(f"{result['product']:14s} ${result['total_cost_usd']:.6f}")
            platform_total += result["total_cost_usd"]
        else:
            print(f"{result['product']:14s} unavailable: {result['reason']}")
    print("=" * 40)
    print(f"{'platform total':14s} ${platform_total:.6f} (reachable products only)")


async def main() -> None:
    parser = argparse.ArgumentParser()
    for product in PRODUCTS:
        parser.add_argument(f"--{product['name']}-url", default=product["default_base_url"])
    args = parser.parse_args()

    base_urls = {
        product["name"]: getattr(args, f"{product['name'].replace('-', '_')}_url")
        for product in PRODUCTS
    }
    results = await build_report(base_urls)
    _print_report(results)


if __name__ == "__main__":
    asyncio.run(main())
