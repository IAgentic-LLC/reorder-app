"""Chapter 9, integration tier: the idempotent job envelope, proven
against the real Postgres this app already runs (see compose.yaml).
Two separate guarantees, tested separately: SAQ's own `key` argument
stops a job from being enqueued twice, and this app's own unique
constraint stops a job's *effect* from happening twice even if SAQ's
own at-least-once delivery runs it more than once anyway.

Each test uses its own `thread_id`, deliberately, a real background
worker may also be running against this same database, a shared id
between tests would race with whatever that worker drains.
"""

import os
import uuid

import psycopg
import pytest
from reorder_app.jobs import get_queue, place_purchase_order
from reorder_app.supplier import SimulatedSupplierClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="No local Postgres configured for this environment, see compose.yaml",
)


async def _delete_ledger_row(thread_id: str) -> None:
    async with await psycopg.AsyncConnection.connect(os.environ["DATABASE_URL"]) as conn:
        await conn.execute("DELETE FROM purchase_orders WHERE thread_id = %s", (thread_id,))
        await conn.commit()


async def test_running_the_job_twice_places_only_one_real_order():
    thread_id = f"purchase-order-test-{uuid.uuid4()}"
    ctx = {"supplier": SimulatedSupplierClient()}
    try:
        first = await place_purchase_order(ctx, thread_id=thread_id, sku="SKU-2040", quantity=5)
        second = await place_purchase_order(ctx, thread_id=thread_id, sku="SKU-2040", quantity=5)

        assert first["already_placed"] is False
        assert second["already_placed"] is True
        assert first["supplier_order_id"] == second["supplier_order_id"]
    finally:
        await _delete_ledger_row(thread_id)


async def test_enqueuing_the_same_key_twice_only_queues_the_job_once():
    thread_id = f"purchase-order-test-{uuid.uuid4()}"
    queue = get_queue()
    await queue.connect()
    try:
        first_job = await queue.enqueue(
            "place_purchase_order",
            key=f"purchase-order:{thread_id}",
            thread_id=thread_id,
            sku="SKU-2040",
            quantity=5,
        )
        second_job = await queue.enqueue(
            "place_purchase_order",
            key=f"purchase-order:{thread_id}",
            thread_id=thread_id,
            sku="SKU-2040",
            quantity=5,
        )
        assert first_job is not None
        assert second_job is None
    finally:
        await queue.disconnect()
        await _delete_ledger_row(thread_id)
