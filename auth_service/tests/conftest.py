import os
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("PEPPER", "test-pepper")
os.environ.setdefault("ADMIN_USER", "test-admin")
os.environ.setdefault("ADMIN_PASS", "test-admin")
os.environ.setdefault("AUTH_MAX_FAILURES", "999999")
os.environ.setdefault("SQLITE_PATH", "/tmp/wicket-test.db")

from main import app  # noqa: E402


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def mock_store(client):
    mock = AsyncMock()
    mock.health.return_value = True
    mock.get_token.return_value = None
    mock.list_tokens.return_value = []
    app.state.store = mock
    yield mock
