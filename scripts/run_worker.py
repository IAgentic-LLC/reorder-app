"""Chapter 9's worker process for reorder-app's background jobs. Two
fixes applied on purpose this time, not rediscovered: `load_dotenv()`
before anything that reads `DATABASE_URL` runs (chapter 6's own
import-order lesson), and the Windows event-loop policy set before
SAQ's own runner builds its loop (chapter 7's fix, same shape, a
different library sitting on the same psycopg async requirement).
"""

import asyncio
import sys

from dotenv import load_dotenv
from saq.runner import start

load_dotenv()

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == "__main__":
    start("reorder_app.jobs.settings")
