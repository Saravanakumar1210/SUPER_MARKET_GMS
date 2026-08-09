"""
Reorganize Cloudinary product images into per-category subfolders.

Current layout:   gms-world-foods/products/<product_id>
Target layout:    gms-world-foods/products/<category-slug>/<product_id>

Steps per image:
  1. Upload (copy) the asset to the new public_id path using Cloudinary rename API
     (if the asset hasn't already been renamed on Cloudinary)
  2. Update the image_url in product_images DB row

Run from the project root:
    python scripts/cloudinary/reorganize_cloudinary_folders.py

Flags:
    --dry-run   Show what would move without touching Cloudinary or DB
    --category  Only process one category slug  (e.g. --category beverages)
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
from pathlib import Path

# Force UTF-8 output on Windows to avoid charmap codec errors
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cloudinary
import cloudinary.uploader
import cloudinary.api

from app.config import get_settings
from app.core.cloudinary_storage import configure_cloudinary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def public_id_from_url(url: str) -> str | None:
    """Extract Cloudinary public_id (no extension) from a secure_url."""
    match = re.search(r"/upload/(?:v\d+/)?(.+)$", url)
    if not match:
        return None
    raw = match.group(1)
    # Strip known image extensions
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if raw.lower().endswith(ext):
            return raw[: -len(ext)]
    return raw


def new_public_id(old_public_id: str, category_slug: str) -> str:
    """
    old_public_id = "gms-world-foods/products/BEV03-CF02-P0001"
    category_slug = "beverages"
    → "gms-world-foods/products/beverages/BEV03-CF02-P0001"
    """
    settings = get_settings()
    base_folder = f"{settings.cloudinary_folder}/products"

    # Strip the base_folder prefix to get just the filename part
    prefix = base_folder + "/"
    if old_public_id.startswith(prefix):
        filename = old_public_id[len(prefix):]
    else:
        # Already in a subfolder — skip if already organized
        filename = old_public_id.split("/")[-1]

    return f"{base_folder}/{category_slug}/{filename}"


def build_new_url(old_url: str, new_pub_id: str) -> str:
    """Reconstruct the Cloudinary URL for the new public_id (no version number)."""
    settings = get_settings()
    cloud = settings.cloudinary_cloud_name
    # Detect format from old URL
    match = re.search(r"/upload/(?:v\d+/)?.+(\.[a-z]+)$", old_url, re.IGNORECASE)
    ext = match.group(1) if match else ".jpg"
    return f"https://res.cloudinary.com/{cloud}/image/upload/{new_pub_id}{ext}"


# ---------------------------------------------------------------------------
# Core async logic
# ---------------------------------------------------------------------------

async def reorganize(
    *,
    dry_run: bool,
    only_category: str | None,
) -> None:
    import asyncpg  # type: ignore
    import ssl as ssl_module

    settings = get_settings()
    configure_cloudinary()

    ctx = ssl_module.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl_module.CERT_NONE

    print(f"Connecting to PostgreSQL …")
    conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        ssl=ctx,
    )

    try:
        # ── Fetch all product images that are still in the flat products/ folder ──
        base_folder = f"{settings.cloudinary_folder}/products"
        # Images already organized have an extra path segment before the product ID
        # e.g. gms-world-foods/products/beverages/BEV03-... has 4 segments
        # Flat ones: gms-world-foods/products/BEV03-...  have 3 segments

        category_filter = ""
        params: list = [f"%cloudinary.com%{base_folder}/%"]

        if only_category:
            category_filter = "AND c.slug = $2"
            params.append(only_category)

        rows = await conn.fetch(
            f"""
            SELECT
                pi.id        AS img_id,
                pi.product_id,
                pi.image_url,
                pi.is_primary,
                c.category_id,
                c.category_name,
                c.slug       AS category_slug
            FROM product_images pi
            JOIN products p  ON p.product_id  = pi.product_id
            JOIN categories c ON c.category_id = p.category_id
            WHERE pi.image_url LIKE $1
            {category_filter}
            ORDER BY c.slug, pi.product_id
            """,
            *params,
        )

        # ── Filter: keep only images that are still in the flat folder ────────
        # i.e. public_id matches  <base_folder>/<product_id>  (no extra slash)
        to_move: list[dict] = []
        already_done = 0

        for r in rows:
            old_pub_id = public_id_from_url(r["image_url"])
            if old_pub_id is None:
                continue

            # Already organized?  public_id = base/products/<slug>/<pid>
            expected_flat = f"{base_folder}/{r['product_id']}"
            if not old_pub_id.startswith(base_folder + "/"):
                continue  # unrelated path, skip

            remainder = old_pub_id[len(base_folder) + 1:]  # e.g. "BEV03-..." or "beverages/BEV03-..."
            if "/" in remainder:
                already_done += 1
                continue  # already in a subfolder

            to_move.append(dict(r))

        print(f"Total images in DB: {len(rows)}")
        print(f"Already organized:  {already_done}")
        print(f"To move:            {len(to_move)}")
        if only_category:
            print(f"Category filter:    {only_category}")
        if dry_run:
            print("Mode: DRY-RUN\n")
        else:
            print()

        if not to_move:
            print("Nothing to do — all images are already organized.")
            return

        # ── Show breakdown by category ──────────────────────────────────────
        from collections import Counter
        cat_counts = Counter(r["category_slug"] for r in to_move)
        print("Move plan by category:")
        for slug, cnt in sorted(cat_counts.items()):
            print(f"  {slug:<45} {cnt:>4} images")
        print()

        if dry_run:
            print("DRY-RUN: showing first 10 moves ...")
            for r in to_move[:10]:
                old_pub_id = public_id_from_url(r["image_url"])
                new_pub = new_public_id(old_pub_id, r["category_slug"])
                print(f"  {r['product_id']}")
                print(f"    FROM: {old_pub_id}")
                print(f"    TO:   {new_pub}")
            return

        # ── Perform the moves ───────────────────────────────────────────────
        ok = failed = 0
        total = len(to_move)

        for idx, r in enumerate(to_move, 1):
            old_pub_id = public_id_from_url(r["image_url"])
            if old_pub_id is None:
                print(f"[{idx:>4}/{total}] {r['product_id']}  SKIP — cannot parse public_id")
                failed += 1
                continue

            new_pub = new_public_id(old_pub_id, r["category_slug"])

            # Skip if old == new (shouldn't happen but guard anyway)
            if old_pub_id == new_pub:
                print(f"[{idx:>4}/{total}] {r['product_id']}  SKIP — already at target path")
                already_done += 1
                continue

            # ── Cloudinary rename (atomic move on Cloudinary side) ────────────
            # Check if already renamed on Cloudinary (previous interrupted run)
            already_at_target = False
            try:
                cloudinary.api.resource(new_pub, resource_type="image")
                already_at_target = True
            except Exception:
                pass  # not found at new path — need to rename

            if not already_at_target:
                try:
                    result = cloudinary.uploader.rename(
                        old_pub_id,
                        new_pub,
                        overwrite=True,
                        resource_type="image",
                    )
                    new_url: str = result["secure_url"]
                except Exception as exc:
                    print(f"[{idx:>4}/{total}] {r['product_id']}  FAIL Cloudinary - {exc}")
                    failed += 1
                    # Small back-off on rate limit errors
                    if "rate" in str(exc).lower():
                        time.sleep(2)
                    continue
            else:
                # Already at new path on Cloudinary — just build the URL
                ext_match = re.search(r"(\.[a-z]+)$", r["image_url"], re.IGNORECASE)
                ext = ext_match.group(1) if ext_match else ".jpg"
                new_url = f"https://res.cloudinary.com/{settings.cloudinary_cloud_name}/image/upload/{new_pub}{ext}"
                print(f"[{idx:>4}/{total}] {r['product_id']}  already on Cloudinary, fixing DB only")

            # ── Update DB ────────────────────────────────────────────────────
            try:
                async with conn.transaction():
                    await conn.execute(
                        "UPDATE product_images SET image_url = $1 WHERE id = $2",
                        new_url,
                        r["img_id"],
                    )
                print(f"[{idx:>4}/{total}] {r['product_id']}  OK  ->  {new_url}")
                ok += 1
            except Exception as exc:
                print(f"[{idx:>4}/{total}] {r['product_id']}  FAIL DB - {exc}")
                failed += 1

            # Cloudinary free tier: ~500 req/hr — small throttle to be safe
            time.sleep(0.3)

        # ── Invalidate cache ────────────────────────────────────────────────
        invalidation_file = ROOT / "app" / "core" / ".cache_invalidated"
        try:
            invalidation_file.touch()
        except OSError:
            pass

        print(f"\n{'='*60}")
        print(f"DONE - OK: {ok}  |  Already done: {already_done}  |  Failed: {failed}  |  Total: {total}")

    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Move Cloudinary product images into per-category subfolders"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    parser.add_argument(
        "--category",
        default=None,
        metavar="SLUG",
        help="Only process one category slug (e.g. beverages)",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.cloudinary_configured:
        raise SystemExit("ERROR: Cloudinary is not configured in .env")

    asyncio.run(reorganize(dry_run=args.dry_run, only_category=args.category))


if __name__ == "__main__":
    main()
