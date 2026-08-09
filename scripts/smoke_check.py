"""
Quick smoke check against a running GMS server.

Usage:
    python run.py
    python scripts/smoke_check.py

Optional:
    python scripts/smoke_check.py --base-url http://127.0.0.1:8002
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request


DEFAULT_CHECKS: tuple[tuple[str, str], ...] = (
    ("GET", "/api/v1/health"),
    ("GET", "/"),
    ("GET", "/products.html"),
    ("GET", "/basket.html"),
    ("GET", "/admin"),
    ("GET", "/css/main.css"),
    ("GET", "/js/main.js"),
)


def _request(method: str, url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.status, response.headers.get("content-type", "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-check a running GMS server")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Server base URL (default: http://127.0.0.1:8000)",
    )
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    failed = 0
    for method, path in DEFAULT_CHECKS:
        url = f"{base}{path}"
        try:
            status, content_type = _request(method, url)
            ok = 200 <= status < 400
            label = "OK" if ok else "FAIL"
            print(f"[{label}] {method} {path} -> {status} ({content_type})")
            if not ok:
                failed += 1
        except urllib.error.URLError as exc:
            print(f"[FAIL] {method} {path} -> {exc}")
            failed += 1

    if failed:
        print(f"\n{failed} check(s) failed. Is the server running? Try: python run.py")
        return 1

    print("\nAll smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
