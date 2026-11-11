"""Tests run against a real PostgreSQL that already has db/init/*.sql loaded.

    DATABASE_URL=postgresql://user:pass@localhost:5432/dbname pytest
"""
import os

import pytest

os.environ.setdefault("ADMIN_PASSWORD", "admin12345")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": os.environ["ADMIN_PASSWORD"]})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
