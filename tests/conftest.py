"""Shared pytest fixtures for API smoke tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _integration_enabled() -> bool:
    return os.getenv("GMS_RUN_INTEGRATION", "").strip().lower() in {"1", "true", "yes"}


@pytest.fixture(scope="session")
def offline_client() -> TestClient:
    """App client with DB/cache warmup disabled (no PostgreSQL required)."""
    noop = AsyncMock(return_value=None)

    with (
        patch("app.main._warmup_db", noop),
        patch("app.main._warmup_catalog_cache", noop),
        patch("app.main._warmup_admin_cache", noop),
    ):
        from app.core.warmup import mark_db_ready, mark_warmup_complete, reset_warmup_state_for_tests
        from app.main import app

        reset_warmup_state_for_tests()
        mark_db_ready()
        mark_warmup_complete()

        with TestClient(app) as client:
            yield client


@pytest.fixture(scope="session")
def integration_client() -> TestClient:
    """Full app client including startup DB warmup (requires configured .env)."""
    if not _integration_enabled():
        pytest.skip("Set GMS_RUN_INTEGRATION=1 to run database integration smoke tests")

    from app.main import app

    with TestClient(app) as client:
        yield client
