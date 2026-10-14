import logging

from shoplite.clients.shipping import ShippingClient
from shoplite.repositories.orders import fetch_order, insert_order
from shoplite.repositories.products import get_product
from shoplite.services.pricing import compute_total
from shoplite.worker import WorkerUnavailable, worker

logger = logging.getLogger(__name__)


class ProductNotFound(Exception):
    pass


def place_order(product_id: int, quantity: int, discount_code: str | None = None) -> dict:
    product = get_product(product_id)
    if product is None:
        raise ProductNotFound(product_id)
    total = compute_total(product["price_cents"], quantity, discount_code)
    shipping = ShippingClient().get_quote(product["weight_grams"] * quantity)
    order_id = insert_order(product_id, quantity, total, shipping)
    try:
        worker.submit({"type": "order_placed", "order_id": order_id})
    except WorkerUnavailable:
        logger.warning("notification deferred for order %s", order_id)
    return {"id": order_id, "total_cents": total, "shipping_cents": shipping}


def get_order(order_id: int) -> dict | None:
    return fetch_order(order_id)
