"""Chapter 9: the reorder agent's approval decision no longer has to wait
for a supplier call before answering. SAQ's queue is the seam; chapter
7's own Postgres is where both the queue's own tables and this chapter's
idempotency ledger live, no second datastore introduced just for this.
"""

import os
import re

import psycopg
from saq.queue.postgres import PostgresQueue

from reorder_app.purchase_orders import already_placed, ensure_table, record_order
from reorder_app.supplier import SimulatedSupplierClient

_SKU_PATTERN = re.compile(r"SKU-\d+")


def extract_sku(question: str) -> str | None:
    """The approval workflow's own state (chapter 7) carries only prose,
    never a structured SKU, `reliable_agents_labs.reorder_workflow`
    wasn't designed to hand one to a caller. This app's own code has to
    recover one from the same question text a person typed, a real,
    narrow seam, not a design choice worth hiding.
    """
    match = _SKU_PATTERN.search(question)
    return match.group(0) if match else None


def _database_url() -> str:
    """Chapter 10's real finding: Fly's attached Postgres offers a
    PgBouncer proxy (port 5432) for connection fan-in, but this app
    already pools client-side (both `AsyncPostgresSaver` and
    `PostgresQueue` carry their own connection pools), so the proxy adds
    nothing and actively breaks things: SAQ's advisory locks and
    psycopg's own server-side prepared statements both need a session
    the pooler's transaction-pooling mode won't hold onto, confirmed
    live by connections dropping mid-query. `DATABASE_URL` on Fly points
    at Postgres directly (port 5433, bypassing the proxy entirely), not
    at the pooler.
    """
    return os.environ["DATABASE_URL"]


def get_queue() -> PostgresQueue:
    return PostgresQueue.from_url(_database_url())


async def startup(ctx: dict) -> None:
    ctx["supplier"] = SimulatedSupplierClient()


async def place_purchase_order(ctx: dict, *, thread_id: str, sku: str, quantity: int) -> dict:
    """The job itself. SAQ's own at-least-once delivery means this can
    run more than once for the same `thread_id`, a worker crash between
    the supplier call succeeding and the job being marked done is
    exactly that case. `already_placed` and `record_order`'s unique
    constraint are what make a second run harmless instead of a second
    real order.
    """
    supplier = ctx["supplier"]
    async with await psycopg.AsyncConnection.connect(_database_url()) as conn:
        await ensure_table(conn)
        existing = await already_placed(conn, thread_id)
        if existing is not None:
            return {
                "thread_id": thread_id,
                "supplier_order_id": existing.supplier_order_id,
                "already_placed": True,
            }

        result = await supplier.place_order(sku, quantity)
        inserted = await record_order(conn, thread_id, sku, quantity, result.order_id)
        return {
            "thread_id": thread_id,
            "supplier_order_id": result.order_id,
            "already_placed": not inserted,
        }


def settings() -> dict:
    """A callable, not a module-level dict, on purpose. Chapter 6 already
    taught this lesson once (`AUTH0_DOMAIN` read before `load_dotenv()`
    ran): a value that depends on the environment shouldn't be computed
    at import time. SAQ's own runner accepts either shape, calling the
    dict-returning form only once it actually starts.
    """
    return {
        "queue": get_queue(),
        "functions": [place_purchase_order],
        "startup": startup,
    }
