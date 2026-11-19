"""
Development-only routes that crash on purpose. They are registered ONLY when
APP_ENV=development (see main.py), so they do not exist in production.
"""
from fastapi import APIRouter
from sqlalchemy import text

from app.dependencies.db import DbSession

router = APIRouter(prefix="/debug", tags=["Debug (development only)"])


@router.get("/crash", summary="Raises ZeroDivisionError (tests the 500 handler)")
def crash():
    return 1 / 0


@router.get("/db-error", summary="Runs invalid SQL (tests a database crash)")
def db_error(db: DbSession):
    db.execute(text("SELECT * FROM table_that_does_not_exist"))