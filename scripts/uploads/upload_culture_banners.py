"""Upload local culture banner images to Cloudinary and create culture banner records."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import asyncio
import re

from app.config import get_settings
from app.core.catalog import invalidate_admin_site_cache
from app.core.cloudinary_storage import upload_file_path
from app.core.culture_order import append_to_tail, load_all_cultures
from app.core.db_indexes import ensure_performance_indexes
from app.database import AsyncSessionLocal
from app.models import CultureBanner
from app.paths import CULTURE_BANNER_SOURCE_DIR

CULTURE_DIR = CULTURE_BANNER_SOURCE_DIR


def _sort_key(path: Path) -> tuple[int, str]:
    match = re.match(r"^(\d+)", path.stem)
    if match:
        return int(match.group(1)), path.stem
    return 9999, path.stem


async def main() -> None:
    if not CULTURE_DIR.is_dir():
        raise SystemExit(f"Culture folder not found: {CULTURE_DIR}")

    images = sorted(
        [p for p in CULTURE_DIR.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}],
        key=_sort_key,
    )
    if not images:
        raise SystemExit(f"No images found in {CULTURE_DIR}")

    settings = get_settings()
    if not settings.cloudinary_configured:
        raise SystemExit("Cloudinary is not configured in .env")

    print(f"Uploading {len(images)} culture banner(s) from {CULTURE_DIR}…")

    async with AsyncSessionLocal() as db:
        await ensure_performance_indexes(db)
        existing = await load_all_cultures(db)
        if existing:
            print(f"Culture banners table already has {len(existing)} row(s) — skipping seed.")
            print("Delete existing culture banners in admin if you want to re-import.")
            return

        for index, img_path in enumerate(images):
            order = _sort_key(img_path)[0] if _sort_key(img_path)[0] != 9999 else index
            print(f"  [{index + 1}/{len(images)}] {img_path.name}…", flush=True)
            result = upload_file_path(
                img_path,
                asset_key=f"culture-banners/culture-{img_path.stem}",
                folder=settings.cloudinary_folder,
            )
            url = result["secure_url"]
            culture = CultureBanner(
                title=f"Culture Banner {order}",
                image_url=url,
                link_url="products.html",
                display_order=order,
                is_active=True,
            )
            db.add(culture)
            await db.flush()
            items = await load_all_cultures(db)
            append_to_tail(culture, items)
            print(f"       {url}")

        await db.commit()

    invalidate_admin_site_cache("cultures")
    print(f"Done — {len(images)} culture banner(s) saved.")


if __name__ == "__main__":
    asyncio.run(main())
