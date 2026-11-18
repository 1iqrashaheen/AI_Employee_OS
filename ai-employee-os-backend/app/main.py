from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

app = FastAPI(title=settings.app_name, version="0.1.0")


@app.get("/api/v1/health", tags=["Health"])
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {
        "success": True,
        "message": "OK",
        "data": {"status": "healthy", "database": "connected"},
    }