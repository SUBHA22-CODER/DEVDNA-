from shoplite.db import get_connection


def list_products() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT id, name, price_cents, weight_grams FROM products ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_product(product_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT id, name, price_cents, weight_grams FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None
