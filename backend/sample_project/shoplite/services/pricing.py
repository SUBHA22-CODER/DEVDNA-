"""Pure pricing rules (no I/O)."""

DISCOUNTS = {"WELCOME10": 10, "VIP20": 20}


def apply_discount(amount_cents: int, code: str | None) -> int:
    percent = DISCOUNTS.get((code or "").upper(), 0)
    return amount_cents - (amount_cents * percent) // 100


def compute_total(price_cents: int, quantity: int, code: str | None = None) -> int:
    if quantity < 1:
        raise ValueError("quantity must be positive")
    return apply_discount(price_cents * quantity, code)
