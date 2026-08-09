"""
Move Cloudinary category images from gms-world-foods/categories/
into gms-world-foods/category images/ and update Neon + frontend fallbacks.

Run from project root:
    python scripts/catalog/reorganize_category_images.py
    python scripts/catalog/reorganize_category_images.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cloudinary.uploader

from app.config import get_settings
from app.core.cloudinary_storage import configure_cloudinary, public_id_from_url

OLD_FOLDER = "categories"
NEW_FOLDER = "category images"
CACHE_FILE = ROOT / "app" / "core" / ".cache_invalidated"
PLACEHOLDERS_FILE = ROOT / "frontend" / "js" / "placeholders.js"


def rewrite_url(old_url: str, cloud_name: str, base_folder: str) -> str:
    if not old_url or "res.cloudinary.com" not in old_url:
        return old_url

    pub_id = public_id_from_url(old_url)
    if not pub_id:
        return old_url

    old_prefix = f"{base_folder}/{OLD_FOLDER}/"
    new_prefix = f"{base_folder}/{NEW_FOLDER}/"
    if not pub_id.startswith(old_prefix):
        return old_url

    new_pub_id = new_prefix + pub_id[len(old_prefix) :]
    ext_match = re.search(r"(\.[a-zA-Z0-9]+)$", old_url)
    ext = ext_match.group(1) if ext_match else ".png"
    return f"https://res.cloudinary.com/{cloud_name}/image/upload/{new_pub_id}{ext}"


def new_public_id(old_url: str, base_folder: str) -> tuple[str, str] | None:
    pub_id = public_id_from_url(old_url)
    if not pub_id:
        return None

    old_prefix = f"{base_folder}/{OLD_FOLDER}/"
    if not pub_id.startswith(old_prefix):
        return None

    filename = pub_id[len(old_prefix) :]
    new_pub = f"{base_folder}/{NEW_FOLDER}/{filename}"
    return pub_id, new_pub


def update_placeholders_file(url_map: dict[str, str]) -> None:
    text = PLACEHOLDERS_FILE.read_text(encoding="utf-8")
    for old_url, new_url in url_map.items():
        text = text.replace(old_url, new_url)
    PLACEHOLDERS_FILE.write_text(text, encoding="utf-8")


async def run(dry_run: bool) -> None:
    import asyncpg
    import ssl as ssl_module

    settings = get_settings()
    base_folder = settings.cloudinary_folder
    configure_cloudinary()

    ssl_ctx = ssl_module.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl_module.CERT_NONE

    conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        ssl=ssl_ctx,
    )

    try:
        rows = await conn.fetch(
            """
            SELECT category_id, category_name, slug, icon_image_url, banner_image_url
            FROM categories
            ORDER BY display_order, category_name
            """
        )

        to_move: list[dict] = []
        already_done = 0

        for row in rows:
            icon = row["icon_image_url"] or ""
            banner = row["banner_image_url"] or ""
            icon_move = new_public_id(icon, base_folder) if icon else None
            banner_move = new_public_id(banner, base_folder) if banner else None

            if not icon_move and not banner_move:
                if NEW_FOLDER.replace(" ", "%20") in icon or NEW_FOLDER in icon:
                    already_done += 1
                continue

            to_move.append(
                {
                    "category_id": row["category_id"],
                    "slug": row["slug"],
                    "icon_old": icon,
                    "banner_old": banner,
                    "icon_move": icon_move,
                    "banner_move": banner_move,
                }
            )

        print(f"Categories total:     {len(rows)}")
        print(f"Already reorganized:  {already_done}")
        print(f"To move:              {len(to_move)}")
        print(f"Target folder:        {base_folder}/{NEW_FOLDER}/")
        if dry_run:
            print("Mode: DRY-RUN\n")

        if not to_move:
            print("Nothing to do.")
            return

        ok = failed = 0
        url_map: dict[str, str] = {}

        for idx, item in enumerate(to_move, 1):
            prefix = f"[{idx}/{len(to_move)}] {item['slug']}"
            renamed_urls: dict[str, str] = {}
            new_icon = item["icon_old"]
            new_banner = item["banner_old"]
            item_failed = False

            for old_url in dict.fromkeys([item["icon_old"], item["banner_old"]]):
                if not old_url:
                    continue
                move = new_public_id(old_url, base_folder)
                if not move:
                    continue
                old_pub, new_pub = move

                if dry_run:
                    print(f"{prefix}  DRY-RUN — {old_pub.split('/')[-1]} -> category images/")
                    continue

                try:
                    result = cloudinary.uploader.rename(
                        old_pub,
                        new_pub,
                        overwrite=True,
                        resource_type="image",
                    )
                    renamed_urls[old_url] = result["secure_url"]
                    url_map[old_url] = result["secure_url"]
                except Exception as exc:
                    print(f"{prefix}  FAIL rename — {exc}")
                    item_failed = True
                    failed += 1
                    break

                time.sleep(0.25)

            if dry_run:
                ok += 1
                continue

            if item_failed:
                continue

            if item["icon_old"] in renamed_urls:
                new_icon = renamed_urls[item["icon_old"]]
            if item["banner_old"] in renamed_urls:
                new_banner = renamed_urls[item["banner_old"]]

            if new_icon == item["icon_old"] and new_banner == item["banner_old"]:
                continue

            try:
                await conn.execute(
                    """
                    UPDATE categories
                    SET icon_image_url = $1,
                        banner_image_url = $2
                    WHERE category_id = $3
                    """,
                    new_icon or None,
                    new_banner or None,
                    item["category_id"],
                )
                print(f"{prefix}  OK")
                ok += 1
            except Exception as exc:
                print(f"{prefix}  FAIL db — {exc}")
                failed += 1

        if not dry_run and url_map:
            update_placeholders_file(url_map)
            try:
                CACHE_FILE.touch()
            except OSError:
                pass

        print(f"\n{'=' * 60}")
        print(f"DONE — OK: {ok}  |  Failed: {failed}  |  Total: {len(to_move)}")
        if dry_run:
            print("(dry-run — no changes were written)")

    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Move category images into category images/ folder")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.cloudinary_configured and not args.dry_run:
        raise SystemExit("ERROR: Cloudinary is not configured in .env")

    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
