import hashlib
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_widgets.db"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.database import Base, get_db
from app.main import app
from app.services import events as events_service
from app.services import geo as geo_service
from app.services import notify
from app.services import pow as pow_service
from app.services.rate_limit import reset as reset_rate_limits

TEST_DB_URL = "sqlite:///./test_widgets.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def _fresh_db_and_toggles():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_rate_limits()
    events_service.reset()
    pow_service.reset()
    geo_service.FORCE_DOWN_A = False
    geo_service.FORCE_DOWN_B = False
    notify.FORCE_FAIL = False
    yield
    Base.metadata.drop_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def tenant_and_key(client):
    resp = client.post(
        "/api/auth/signup", json={"email": "test@example.com", "password": "password123"}
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def widget(client, tenant_and_key):
    resp = client.post(
        "/api/widgets",
        headers={"X-API-Key": tenant_and_key["api_key"]},
        json={
            "type": "signup_form",
            "title": "Join us",
            "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}],
        },
    )
    assert resp.status_code == 201
    return resp.json()


def solve_pow_challenge(client, widget_id: str) -> dict:
    """Fetches a real proof-of-work challenge and actually solves it — the
    exact same brute-force algorithm the widget bundle runs client-side via
    Web Crypto (see app/routers/public.py's _WIDGET_JS), just in Python.
    Returns the two fields a submission payload needs to pass bot defense."""
    resp = client.get(f"/widgets/{widget_id}/challenge")
    assert resp.status_code == 200
    challenge = resp.json()
    salt = challenge["salt"]
    prefix = "0" * challenge["difficulty"]
    counter = 0
    while True:
        solution = str(counter)
        digest = hashlib.sha256((salt + solution).encode()).hexdigest()
        if digest.startswith(prefix):
            return {"challenge_id": challenge["challenge_id"], "solution": solution}
        counter += 1
