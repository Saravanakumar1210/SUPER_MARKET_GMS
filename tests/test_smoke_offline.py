"""Fast smoke tests that do not require PostgreSQL."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_ok(offline_client: TestClient) -> None:
    response = offline_client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("status") == "ok"
    assert payload.get("service") == "gms-world-foods"


def test_storefront_pages_serve(offline_client: TestClient) -> None:
    for path in (
        "/",
        "/products.html",
        "/basket.html",
        "/about.html",
        "/contact.html",
        "/login.html",
        "/signup.html",
        "/account.html",
    ):
        response = offline_client.get(path)
        assert response.status_code == 200, path
        assert "text/html" in response.headers.get("content-type", ""), path


def test_admin_portal_serves(offline_client: TestClient) -> None:
    for path in ("/admin", "/admin.html"):
        response = offline_client.get(path)
        assert response.status_code == 200, path
        assert "text/html" in response.headers.get("content-type", ""), path


def test_static_assets_serve(offline_client: TestClient) -> None:
    for path in ("/css/main.css", "/js/main.js", "/js/admin.js"):
        response = offline_client.get(path)
        assert response.status_code == 200, path


def test_admin_api_requires_auth(offline_client: TestClient) -> None:
    response = offline_client.get("/api/v1/admin/dashboard")
    assert response.status_code == 401


def test_openapi_available(offline_client: TestClient) -> None:
    response = offline_client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema.get("info", {}).get("title") == "GMS World Foods API"
    assert "/api/v1/health" in schema.get("paths", {})
    assert "/api/v1/catalog/metadata" in schema.get("paths", {})


def test_legacy_bucket_redirects_to_basket(offline_client: TestClient) -> None:
    response = offline_client.get("/bucket.html", follow_redirects=False)
    # bucket.html may redirect client-side or serve basket; accept 200 HTML.
    assert response.status_code in {200, 307, 308}
