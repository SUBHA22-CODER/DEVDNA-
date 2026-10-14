from contextlib import asynccontextmanager

from fastapi import FastAPI

from shoplite.db import init_db
from shoplite.routes import health, orders, products, shipping
from shoplite.worker import worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    worker.start()
    yield


app = FastAPI(title="ShopLite", lifespan=lifespan)
app.include_router(health.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(shipping.router)
