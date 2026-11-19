from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db

# Use `db: DbSession` in any endpoint to get a database session.
DbSession = Annotated[Session, Depends(get_db)]