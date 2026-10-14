from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from shoplite.clients.shipping import ShippingUnavailable
from shoplite.services.orders import ProductNotFound, get_order, place_order

router = APIRouter(prefix="/api/orders")


class OrderIn(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, le=100)
    discount_code: str | None = None


@router.post("", status_code=201)
def create_order(payload: OrderIn):
    try:
        return place_order(payload.product_id, payload.quantity, payload.discount_code)
    except ProductNotFound:
        raise HTTPException(status_code=404, detail="product not found")
    except ShippingUnavailable:
        raise HTTPException(status_code=503, detail="shipping provider unavailable")


@router.get("/{order_id}")
def read_order(order_id: int):
    order = get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    return order
