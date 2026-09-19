"""Chapter 35, unit tier: the one piece of `platform_cost_report.py`
that doesn't need a real network call. Same reasoning chapter 32 already
used for `synthetic_load_agent.py`, an operational script that hits a
real target gets tested at the seams that don't require one.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from platform_cost_report import missing_credential_reason  # noqa: E402


def test_a_fully_configured_product_has_no_missing_credential_reason():
    env = {
        "AUTH0_TEST_CLIENT_ID": "id",
        "AUTH0_TEST_CLIENT_SECRET": "secret",
        "AUTH0_DOMAIN": "tenant.auth0.com",
        "AUTH0_AUDIENCE": "https://example.dev/api",
    }
    assert missing_credential_reason(env) is None


def test_triage_apps_real_configuration_is_reported_as_missing():
    """`triage-app`'s own `.env` really has `AUTH0_DOMAIN`/`AUTH0_AUDIENCE`
    but no M2M client at all, chapter 22's still-open, real finding.
    """
    env = {"AUTH0_DOMAIN": "tenant.auth0.com", "AUTH0_AUDIENCE": "https://triage-app.dev/api"}
    assert missing_credential_reason(env) is not None


def test_an_empty_env_is_reported_as_missing():
    assert missing_credential_reason({}) is not None
