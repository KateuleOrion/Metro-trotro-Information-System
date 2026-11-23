"""Test setup. The tests run against a REAL PostgreSQL database that is reset before every test
by loading the team's metro_trotro_db.sql.

WARNING: use a separate database for testing. Its data is erased every time.

    createdb metro_trotro_test
    set TEST_DATABASE_URL=postgresql://postgres:password@localhost:5432/metro_trotro_test
    pytest
"""
import os
import sys
from pathlib import Path

import psycopg
import pytest

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DB_URL:
    raise SystemExit(
        "Set TEST_DATABASE_URL to a SEPARATE test database (its data is erased by the tests). "
        "Example: postgresql://postgres:password@localhost:5432/metro_trotro_test"
    )
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ.setdefault("JWT_SECRET", "test-secret-used-only-by-the-automated-tests")

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


def _schema_file() -> Path:
    if os.environ.get("SCHEMA_FILE"):
        return Path(os.environ["SCHEMA_FILE"])
    for candidate in (
        BACKEND_DIR.parent / "metro_trotro_db.sql",
        BACKEND_DIR.parent / "database" / "metro_trotro_db.sql",
        BACKEND_DIR / "metro_trotro_db.sql",
    ):
        if candidate.exists():
            return candidate
    raise SystemExit("Cannot find metro_trotro_db.sql. Set SCHEMA_FILE to its path.")


SCHEMA_SQL = _schema_file().read_text(encoding="utf-8")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.routers import auth as auth_router  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def fresh_database():
    """Reset the data (and the in-memory login limiter) before every test."""
    with psycopg.connect(TEST_DB_URL, autocommit=True) as conn:
        conn.execute(SCHEMA_SQL)
    auth_router._failures.clear()


@pytest.fixture
def db():
    """Direct database access for checking results and arranging special situations."""
    with psycopg.connect(TEST_DB_URL, autocommit=True, row_factory=psycopg.rows.dict_row) as conn:
        yield conn


def _login(client, email, password):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def manager(client):
    return _login(client, "demo@station.com", "demo123")


@pytest.fixture
def staff(client):
    return _login(client, "ama@station.com", "staff123")
