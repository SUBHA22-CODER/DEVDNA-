import pytest

from shoplite.services.pricing import apply_discount, compute_total
from shoplite.worker import NotificationWorker


def test_compute_total_without_discount():
    assert compute_total(1000, 3) == 3000


def test_discount_codes():
    assert apply_discount(10000, "vip20") == 8000
    assert apply_discount(10000, "unknown") == 10000


def test_quantity_must_be_positive():
    with pytest.raises(ValueError):
        compute_total(1000, 0)


def test_worker_delivers_events():
    w = NotificationWorker()
    w.start()
    w.submit({"type": "ping"})
    w.drain()
    assert w.delivered == [{"type": "ping"}]
