"""
Reorganize Cloudinary product images into category sub-folders.

Current state:
  gms-world-foods/products/<product_id>          ← flat (need moving)
  gms-world-foods/products/<category>/<product_id>  ← already organized

This script:
  1. Fetches ALL resources under gms-world-foods/products
  2. For every flat image, looks up its category in PostgreSQL
  3. Renames (moves) the asset to gms-world-foods/products/<category-slug>/<product_id>
     via cloudinary.uploader.rename()
  4. Updates product_images.image_url in the DB
  5. Touches .cache_invalidated so the live site picks up new URLs

Also handles the case where images already ARE in a category folder but in the
WRONG category (safety check).

Run from project root:
    python scripts/cloudinary/reorganize_cloudinary.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cloudinary
import cloudinary.api
import cloudinary.uploader

from app.config import get_settings

# ── Category slug mapping (matches what's already in Cloudinary) ─────────────
# category_name (lower, stripped) → cloudinary folder slug
CATEGORY_SLUG_MAP = {
    "dry grocery & staples": "dry-grocery-staples",
    "bakery, pasta & noodles": "bakery-pasta-noodles",
    "beverages": "beverages",
    "fresh produce": "fresh-produce",
    "frozen, meat & ready-to-cook": "frozen-meat-ready-to-cook",
    "condiments, sauces & pickles": "condiments-sauces-pickles",
    "dairy, eggs & chilled": "dairy-eggs-chilled",
    "household & personal care": "household-personal-care",
    "snacks & confectionery": "snacks-confectionery",
}

# Also map by category_id prefix (first 3 chars of product_id)
# e.g. DGS → dry-grocery-staples
CATEGORY_ID_PREFIX_MAP = {
    "DGS": "dry-grocery-staples",
    "BPN": "bakery-pasta-noodles",
    "BEV": "beverages",
    "FRP": "fresh-produce",
    "FRZ": "frozen-meat-ready-to-cook",
    "CSP": "condiments-sauces-pickles",
    "DEC": "dairy-eggs-chilled",
    "HPC": "household-personal-care",
    "SNC": "snacks-confectionery",
}

CACHE_FILE = ROOT / "app" / "core" / ".cache_invalidated"


def slug_for_category(category_name: str) -> str | None:
    return CATEGORY_SLUG_MAP.get(category_name.lower().strip())


def slug_from_product_id(product_id: str) -> str | None:
    """Fast lookup from the 3-char category prefix in the product ID."""
    prefix = product_id[:3].upper()
    return CATEGORY_ID_PREFIX_MAP.get(prefix)


def fetch_all_resources(prefix: str) -> list[dict]:
    """Page through Cloudinary and return all resources under prefix."""
    resources = []
    next_cursor = None
    while True:
        kwargs = dict(type="upload", prefix=prefix, max_results=500)
        if next_cursor:
            kwargs["next_cursor"] = next_cursor
        result = cloudinary.api.resources(**kwargs)
        resources.extend(result["resources"])
        next_cursor = result.get("next_cursor")
        if not next_cursor:
            break
    return resources


async def load_product_category_map(conn) -> dict[str, str]:
    """Return {product_id: category_name} for all products."""
    rows = await conn.fetch("""
        SELECT p.product_id, c.category_name
        FROM products p
        JOIN categories c ON c.category_id = p.category_id
    """)
    return {r["product_id"]: r["category_name"] for r in rows}


async def run(dry_run: bool) -> None:
    import asyncpg  # type: ignore
    import ssl as ssl_module

    s = get_settings()
    cloudinary.config(
        cloud_name=s.cloudinary_cloud_name,
        api_key=s.cloudinary_api_key,
        api_secret=s.cloudinary_api_secret,
        secure=True,
    )

    PRODUCTS_PREFIX = f"{s.cloudinary_folder}/products"

    # ── 1. Connect to DB ──────────────────────────────────────────────────────
    ssl_ctx = ssl_module.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl_module.CERT_NONE
    print(f"Connecting to PostgreSQL …")
    conn = await asyncpg.connect(
        host=s.db_host, port=s.db_port,
        database=s.db_name, user=s.db_user, password=s.db_password,
        ssl=ssl_ctx,
    )

    try:
        cat_map = await load_product_category_map(conn)
        print(f"Loaded {len(cat_map)} product-category mappings from DB\n")

        # ── 2. Fetch all Cloudinary resources ─────────────────────────────────
        print(f"Fetching all Cloudinary resources under {PRODUCTS_PREFIX} …")
        resources = fetch_all_resources(PRODUCTS_PREFIX)
        print(f"Found {len(resources)} total resources\n")

        # ── 3. Build work list ────────────────────────────────────────────────
        # We want to move EVERY image that is NOT already in the correct folder.
        # That covers:
        #   a) flat images: gms-world-foods/products/<product_id>
        #   b) images in wrong category (safety)
        to_move: list[tuple[str, str, str, str]] = []  # (product_id, old_pid, new_pid, new_url)
        already_correct = 0
        unknown_cat = []

        for r in resources:
            old_pid: str = r["public_id"]
            old_url: str = r["secure_url"]
            ext = Path(old_pid.split("/")[-1] + "." + r.get("format", "jpg")).suffix

            # Extract product_id — it's always the last segment of the public_id
            product_id = old_pid.split("/")[-1]

            # Determine correct category slug
            cat_name = cat_map.get(product_id)
            if cat_name:
                correct_slug = slug_for_category(cat_name)
            else:
                # Fall back to prefix heuristic
                correct_slug = slug_from_product_id(product_id)

            if not correct_slug:
                unknown_cat.append((product_id, old_pid))
                continue

            new_pid = f"{PRODUCTS_PREFIX}/{correct_slug}/{product_id}"

            if old_pid == new_pid:
                already_correct += 1
                continue

            # Build new URL — we reconstruct it after rename
            # Format is preserved by Cloudinary rename
            fmt = r.get("format", "jpg")
            new_url = f"https://res.cloudinary.com/{s.cloudinary_cloud_name}/image/upload/{new_pid}.{fmt}"
            to_move.append((product_id, old_pid, new_pid, new_url))

        print(f"Already in correct folder:  {already_correct}")
        print(f"Need to move:               {len(to_move)}")
        print(f"Unknown category (skip):    {len(unknown_cat)}")
        if unknown_cat:
            print("  Unknown:")
            for pid, pub in unknown_cat[:10]:
                print(f"    {pid}  ({pub})")

        if not to_move:
            print("\nNothing to move. All images are already organized.")
            return

        print()
        if dry_run:
            print("DRY-RUN — no changes will be made.\n")

        # ── 4. Rename in Cloudinary + update DB ──────────────────────────────
        ok = failed = db_updated = 0

        for idx, (product_id, old_pid, new_pid, new_url) in enumerate(to_move, 1):
            prefix_str = f"[{idx:>4}/{len(to_move)}] {product_id}"

            if dry_run:
                print(f"{prefix_str}  DRY-RUN  {old_pid.split('/')[-2] if '/' in old_pid else 'flat'}  ->  {new_pid.split('/')[-2]}/")
                ok += 1
                continue

            # Rename (move) in Cloudinary
            try:
                cloudinary.uploader.rename(
                    old_pid,
                    new_pid,
                    overwrite=True,
                    resource_type="image",
                )
            except Exception as exc:
                print(f"{prefix_str}  FAIL rename — {exc}")
                failed += 1
                continue

            # Update DB — find the row by the OLD url pattern and update it
            try:
                # Match by product_id + is_primary since old URL version number varies
                updated = await conn.execute(
                    """
                    UPDATE product_images
                    SET image_url = $1
                    WHERE product_id = $2
                      AND image_url LIKE $3
                    """,
                    new_url,
                    product_id,
                    f"%/products/%{product_id}%",
                )
                rows_affected = int(updated.split()[-1])
                db_updated += rows_affected
                print(f"{prefix_str}  OK  (DB rows: {rows_affected})  ->  .../{new_pid.split('/', 2)[-1]}")
            except Exception as exc:
                print(f"{prefix_str}  FAIL db — {exc}")
                failed += 1
                continue

            ok += 1

        # ── 5. Invalidate cache ───────────────────────────────────────────────
        if not dry_run and ok > 0:
            try:
                CACHE_FILE.touch()
                print(f"\nCache invalidation file touched: {CACHE_FILE}")
            except OSError:
                pass

        print(f"\n{'='*62}")
        print(f"DONE — Moved: {ok}  |  Failed: {failed}  |  DB rows: {db_updated}  |  Total: {len(to_move)}")
        if dry_run:
            print("(dry-run — no changes were written)")

    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reorganize Cloudinary product images into category folders")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without executing")
    args = parser.parse_args()

    s = get_settings()
    if not s.cloudinary_configured:
        raise SystemExit("ERROR: Cloudinary is not configured. Set CLOUDINARY_* in .env")

    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
