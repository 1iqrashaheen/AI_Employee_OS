import pytest
from sqlalchemy import JSON, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.dependencies.db import get_db
from app.main import app
from app.db.base import Base
from app.models import Company, Customer, Record, Task, User


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # The PostgreSQL-specific ARRAY/JSONB columns are replaced with their JSON
    # equivalents for this isolated SQLite test database.
    Customer.__table__.c.tags.type = JSON()
    Customer.__table__.c.tags.server_default = None
    Record.__table__.c.data.type = JSON()
    Record.__table__.c.data.server_default = None
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_engine):
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
