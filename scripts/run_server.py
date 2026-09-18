"""Chapter 10: the same launcher chapter 7's `run_dev_server.py` proved,
generalized for a real container instead of one developer's own
machine. Two things a container needs that `localhost` never did:
binding `0.0.0.0`, not `127.0.0.1`, since Fly's proxy connects to the
container over its private network, not loopback, and reading `PORT`
from the environment, Fly's own convention, instead of a number typed
into the source.
"""

import asyncio
import os
import sys

import uvicorn

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    port = int(os.environ.get("PORT", "8000"))
    config = uvicorn.Config("reorder_app.api:app", host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())
