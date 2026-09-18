"""Chapter 7's real fix for a real, live-discovered problem, take two.

Setting the event loop policy before `import uvicorn` was not enough:
`uvicorn.run()` wraps its own `asyncio.run()` call, and that call's own
loop setup resets the policy back to Windows' default ProactorEventLoop
regardless of what was set beforehand, verified live, not assumed.
The fix that actually works: build the event loop directly, right after
setting the policy, and hand `uvicorn.Server.serve()` to that loop
ourselves, bypassing `uvicorn.run()`'s own loop management entirely.
"""

import asyncio
import sys

import uvicorn

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    config = uvicorn.Config("reorder_app.api:app", host="127.0.0.1", port=8000)
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())
