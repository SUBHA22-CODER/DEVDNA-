# ShopLite (DevDNA sample project)

A deliberately small FastAPI shop used to demonstrate DevDNA end to end.

- `shoplite/routes/`: HTTP endpoints (health, products, orders, shipping)
- `shoplite/services/`: business logic (pricing, order placement)
- `shoplite/repositories/`: SQLite data access
- `shoplite/clients/shipping.py`: external shipping-rates API client (mocked locally in tests)
- `shoplite/worker.py`: in-process background notification worker
- `tests/`: pytest suite using a disposable SQLite database and a local mock transport

No network, real database or API key is needed. Run `python -m pytest -q`.
