from fastapi import APIRouter, HTTPException

from shoplite.clients.shipping import ShippingClient, ShippingUnavailable

router = APIRouter()


@router.get("/api/shipping/quote")
def shipping_quote(weight_grams: int):
    try:
        return {"price_cents": ShippingClient().get_quote(weight_grams)}
    except ShippingUnavailable:
        raise HTTPException(status_code=503, detail="shipping provider unavailable")
