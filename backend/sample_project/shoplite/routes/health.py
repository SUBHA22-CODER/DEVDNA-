import sqlite3

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from shoplite.db import check_db

router = APIRouter()


@router.get("/health")
def health():
    try:
        check_db()
    except sqlite3.Error:
        return JSONResponse({"status": "degraded", "database": "unavailable"}, status_code=503)
    return {"status": "ok", "database": "ok"}
