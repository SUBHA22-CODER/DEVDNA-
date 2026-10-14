from fastapi import APIRouter, HTTPException

from shoplite.repositories.products import get_product, list_products

router = APIRouter(prefix="/api/products")


@router.get("")
def read_products():
    return list_products()


@router.get("/{product_id}")
def read_product(product_id: int):
    product = get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")
    return product
