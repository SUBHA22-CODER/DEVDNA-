"""Client for the external shipping-rates API.

In tests TRANSPORT is replaced by a local httpx.MockTransport, so no real
network traffic is ever produced.
"""
import os

import httpx

TRANSPORT: httpx.BaseTransport | None = None


class ShippingUnavailable(Exception):
    pass


class ShippingClient:
    def __init__(self) -> None:
        self.base_url = os.environ["SHIPPING_API_URL"]
        self.http = httpx.Client(transport=TRANSPORT, timeout=3.0)

    def get_quote(self, weight_grams: int) -> int:
        try:
            response = self.http.get(f"{self.base_url}/quote", params={"weight": weight_grams})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ShippingUnavailable(str(exc)) from exc
        return int(response.json()["price_cents"])
