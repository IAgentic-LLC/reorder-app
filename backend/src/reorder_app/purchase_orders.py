"""Chapter 9's idempotency ledger. `thread_id` is the primary key, on
purpose: a unique constraint is what actually makes a retried or
duplicated job safe, not application code trying to remember what it
already did. The same Postgres this app already runs (chapter 7), no new
datastore introduced just to back a queue.
"""

import psycopg
from pydantic import BaseModel

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS purchase_orders (
    thread_id TEXT PRIMARY KEY,
    sku TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    supplier_order_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


class PurchaseOrderRecord(BaseModel):
    thread_id: str
    sku: str
    quantity: int
    supplier_order_id: str


async def ensure_table(conn: psycopg.AsyncConnection) -> None:
    await conn.execute(CREATE_TABLE_SQL)
    await conn.commit()


async def already_placed(
    conn: psycopg.AsyncConnection, thread_id: str
) -> PurchaseOrderRecord | None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT thread_id, sku, quantity, supplier_order_id "
            "FROM purchase_orders WHERE thread_id = %s",
            (thread_id,),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return PurchaseOrderRecord(
        thread_id=row[0], sku=row[1], quantity=row[2], supplier_order_id=row[3]
    )


async def record_order(
    conn: psycopg.AsyncConnection,
    thread_id: str,
    sku: str,
    quantity: int,
    supplier_order_id: str,
) -> bool:
    """Inserts the ledger row for a newly placed order. Returns True if
    this call actually inserted it, False if another attempt already
    had, `ON CONFLICT DO NOTHING` is the actual idempotency guarantee,
    not a check-then-insert this code could still race.
    """
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO purchase_orders (thread_id, sku, quantity, supplier_order_id) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (thread_id) DO NOTHING",
            (thread_id, sku, quantity, supplier_order_id),
        )
        inserted = cur.rowcount == 1
    await conn.commit()
    return inserted
