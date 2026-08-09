"""Upload category thumbnail images from data/source-images/categories/ to Cloudinary."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.config import get_settings
from app.core.cloudinary_storage import upload_file_path
from app.paths import CATEGORY_SOURCE_IMAGES_DIR

CATEGORIES = [
    "dry-grocery-staples",
    "snacks-confectionery",
    "beverages",
    "fresh-produce",
    "frozen-meat-ready-to-cook",
    "condiments-sauces-pickles",
    "dairy-eggs-chilled",
    "household-personal-care",
    "bakery-pasta-noodles",
]


def main() -> None:
    settings = get_settings()
    if not settings.cloudinary_configured:
        raise SystemExit("Cloudinary is not configured in .env")

    if not CATEGORY_SOURCE_IMAGES_DIR.is_dir():
        raise SystemExit(f"Category images folder not found: {CATEGORY_SOURCE_IMAGES_DIR}")

    results: dict[int, tuple[str, str]] = {}
    for i, slug in enumerate(CATEGORIES, start=1):
        fpath = CATEGORY_SOURCE_IMAGES_DIR / f"{i}.png"
        if not fpath.is_file():
            print(f"[{i}/9] SKIP — missing {fpath.name}")
            continue
        print(f"[{i}/9] Uploading {fpath.name} -> Category Images/{slug}")
        result = upload_file_path(
            fpath,
            asset_key=f"Category Images/{slug}",
            folder=settings.cloudinary_folder,
        )
        url = result["secure_url"]
        results[i] = (slug, url)
        print(f"      OK: {url}")

    print("\n--- UPLOAD COMPLETE ---")
    for idx, (slug, url) in results.items():
        print(f"{idx}. {slug}: {url}")


if __name__ == "__main__":
    main()
