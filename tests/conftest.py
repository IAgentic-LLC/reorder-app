"""Loads .env once for the whole test session, same pattern as reliable-agents-labs."""

import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

if sys.platform == "win32":
    # Chapter 7's real, live finding: psycopg's async mode refuses to
    # run on Windows' default ProactorEventLoop at all ("Psycopg cannot
    # use the 'ProactorEventLoop' to run in async mode"), a real
    # platform gotcha, not a hypothetical one, caught the first time
    # the integration test actually ran on this machine. The selector
    # loop policy is psycopg's own documented fix.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
