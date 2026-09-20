"""Chapter 7: real, shared, durable persistence, using a seam Book 2
already built rather than touching Book 2's code at all.

`reliable_agents_labs.reorder_workflow.build_approval_workflow` accepts
any LangGraph checkpointer. Book 2 compiles it with `AsyncSqliteSaver`,
one file on disk, fine for a single book chapter's demonstration. This
module compiles the exact same, unchanged workflow with
`AsyncPostgresSaver` instead, a real shared database two separate
processes can both read and write, which is the actual point: chapter 4
promised this chapter would replace a module-level dict with something
real, this is what "real" means for a workflow's own paused state.
"""

import os

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from reliable_agents_labs.models import ModelClient
from reliable_agents_labs.reorder_workflow import build_approval_workflow


def _database_url() -> str:
    # Lazy, same lesson as chapter 6's auth.py: read config when it's
    # actually needed, not at import time.
    return os.environ["DATABASE_URL"]


def get_postgres_checkpointer():
    """Returns an async context manager, the same shape Book 2's own
    `build_checkpointer()` already has, `async with get_postgres_checkpointer() as saver:`.
    """
    return AsyncPostgresSaver.from_conn_string(_database_url())


async def build_persistent_approval_workflow(checkpointer, model_client: ModelClient | None = None):
    """Compiles Book 2's approval workflow, unchanged, with a real
    Postgres-backed checkpointer instead of Book 2's own SQLite one.
    `checkpointer` is passed in rather than constructed here, so a
    caller controls its lifetime (one connection pool for the whole
    app, not one per request).
    """
    return build_approval_workflow(model_client=model_client, checkpointer=checkpointer)
