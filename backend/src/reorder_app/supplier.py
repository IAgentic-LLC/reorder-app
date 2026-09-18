"""Chapter 9: the boundary a real reorder product would eventually cross,
a supplier's own ordering API. No such API exists for this book to call,
there is no shared purchasing service every reader could safely hit, so
what's real here is the shape that boundary has to have, not the supplier
itself. `SupplierClient` is the same kind of seam chapter 5's `ModelClient`
already is: a real implementation and a scripted one, both behind one
interface, so nothing calling it needs to know which one it got.
"""

import uuid

from pydantic import BaseModel


class SupplierOrderResult(BaseModel):
    order_id: str
    sku: str
    quantity: int


class SupplierClient:
    async def place_order(self, sku: str, quantity: int) -> SupplierOrderResult:
        raise NotImplementedError


class SimulatedSupplierClient(SupplierClient):
    """Stands in for a real supplier's ordering API. Chapter 9's actual
    subject is the job envelope wrapped around this call, not this call.
    """

    async def place_order(self, sku: str, quantity: int) -> SupplierOrderResult:
        order_id = f"po_{uuid.uuid4().hex[:12]}"
        return SupplierOrderResult(order_id=order_id, sku=sku, quantity=quantity)
