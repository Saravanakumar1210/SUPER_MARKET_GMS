"""Database-backed smoke tests (optional)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_catalog_metadata_shape(integration_client: TestClient) -> None:
    response = integration_client.get("/api/v1/catalog/metadata")
    assert response.status_code == 200
    payload = response.json()
    assert "categories" in payload
    assert "subcategories" in payload
    assert isinstance(payload["categories"], list)


def test_catalog_home_products_shape(integration_client: TestClient) -> None:
    response = integration_client.get("/api/v1/catalog/home-products")
    assert response.status_code == 200
    payload = response.json()
    assert "products" in payload
    assert isinstance(payload["products"], list)


def test_public_coupons_active(integration_client: TestClient) -> None:
    response = integration_client.get("/api/v1/coupons/active")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
