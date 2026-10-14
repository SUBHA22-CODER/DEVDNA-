"""SQLite access layer."""
import sqlite3

from shoplite.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    price_cents INTEGER NOT NULL,
    weight_grams INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    total_cents INTEGER NOT NULL,
    shipping_cents INTEGER NOT NULL
);
"""

SEED = [
    (1, "Mechanical Keyboard", 8900, 900),
    (2, "USB-C Hub", 3900, 200),
    (3, "Monitor Arm", 12900, 3500),
]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_settings().database_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    with conn:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT OR IGNORE INTO products VALUES (?, ?, ?, ?)", SEED)
    conn.close()


def check_db() -> bool:
    conn = get_connection()
    try:
        conn.execute("SELECT 1")
        return True
    finally:
        conn.close()
