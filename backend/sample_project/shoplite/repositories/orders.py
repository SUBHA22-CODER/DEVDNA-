from shoplite.db import get_connection


def insert_order(product_id: int, quantity: int, total_cents: int, shipping_cents: int) -> int:
    conn = get_connection()
    with conn:
        cur = conn.execute(
            "INSERT INTO orders (product_id, quantity, total_cents, shipping_cents) VALUES (?, ?, ?, ?)",
            (product_id, quantity, total_cents, shipping_cents),
        )
    order_id = cur.lastrowid
    conn.close()
    return order_id


def fetch_order(order_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    return dict(row) if row else None
