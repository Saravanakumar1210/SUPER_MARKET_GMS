"""Upload local banner images to Cloudinary and create hero slide records."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import asyncio
import re

from app.config import get_settings
from app.core.catalog import invalidate_admin_site_cache
from app.core.cloudinary_storage import upload_file_path
from app.database import AsyncSessionLocal
from app.models import SiteBanner
from app.paths import HERO_BANNER_SOURCE_DIR

BANNER_DIR = HERO_BANNER_SOURCE_DIR


def _sort_key(path: Path) -> tuple[int, str]:
    match = re.match(r"^(\d+)", path.stem)
    if match:
        return int(match.group(1)), path.stem
    return 9999, path.stem


async def main() -> None:
    if not BANNER_DIR.is_dir():
        raise SystemExit(f"Banner folder not found: {BANNER_DIR}")

    images = sorted(
        [p for p in BANNER_DIR.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}],
        key=_sort_key,
    )
    if not images:
        raise SystemExit(f"No images found in {BANNER_DIR}")

    settings = get_settings()
    if not settings.cloudinary_configured:
        raise SystemExit("Cloudinary is not configured in .env")

    print(f"Uploading {len(images)} banner(s) from {BANNER_DIR}…")

    async with AsyncSessionLocal() as db:
        for index, img_path in enumerate(images):
            order = _sort_key(img_path)[0] if _sort_key(img_path)[0] != 9999 else index
            print(f"  [{index + 1}/{len(images)}] {img_path.name}…", flush=True)
            result = upload_file_path(
                img_path,
                asset_key=f"promotion-banners/hero-{img_path.stem}",
                folder=settings.cloudinary_folder,
            )
            url = result["secure_url"]
            banner = SiteBanner(
                title=f"Hero Slide {order}",
                subtitle=None,
                image_url=url,
                link_url=None,
                display_order=order,
                is_active=True,
            )
            db.add(banner)
            print(f"       {url}")

        await db.commit()

    invalidate_admin_site_cache("banners")
    print(f"Done — {len(images)} hero slide(s) saved.")


if __name__ == "__main__":
    asyncio.run(main())
