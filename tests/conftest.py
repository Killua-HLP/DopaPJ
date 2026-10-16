import atexit
import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import URL

_database_file = Path(tempfile.gettempdir()) / f"anime-hub-tests-{os.getpid()}.sqlite3"
os.environ["DB_URL"] = URL.create("sqlite", database=str(_database_file)).render_as_string(
    hide_password=False
)
os.environ["SECRET_KEY"] = "pytest-only-secret-key"

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.security import rate_limiter
from app.main import app


def _clean_up_database() -> None:
    engine.dispose()
    _database_file.unlink(missing_ok=True)


atexit.register(_clean_up_database)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_database():
    rate_limiter.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
