"""
Fix Cloudinary Media Library placement for category images.

Renaming public_id alone left asset_folder empty, so images appear loose in Home.
This script assigns asset_folder = gms-world-foods/Category Images and removes
legacy numbered duplicates in gms-world-foods/categories/.

Run:
    python scripts/catalog/fix_category_image_folders.py
    python scripts/catalog/fix_category_image_folders.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
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

import cloudinary.api
import cloudinary.uploader

from app.config import get_settings
from app.core.cloudinary_storage import configure_cloudinary, public_id_from_url

TARGET_ASSET_FOLDER = "Category Images"
LEGACY_NUMBERS = tuple(str(i) for i in range(1, 10))


def list_category_public_ids(base_folder: str) -> list[str]:
    prefixes = (
        f"{base_folder}/category images",
        f"{base_folder}/Category Images",
        f"{base_folder}/categories",
    )
    found: list[str] = []
    seen: set[str] = set()
    for prefix in prefixes:
        next_cursor = None
        while True:
            kwargs = dict(type="upload", prefix=prefix, max_results=500)
            if next_cursor:
                kwargs["next_cursor"] = next_cursor
            result = cloudinary.api.resources(**kwargs)
            for resource in result.get("resources", []):
                pid = resource["public_id"]
                if pid not in seen:
                    seen.add(pid)
                    found.append(pid)
            next_cursor = result.get("next_cursor")
            if not next_cursor:
                break
    return sorted(found)


def is_legacy_numbered(pid: str, base_folder: str) -> bool:
    suffix = pid.removeprefix(f"{base_folder}/categories/")
    return suffix in LEGACY_NUMBERS


def is_active_category_image(pid: str, base_folder: str) -> bool:
    if is_legacy_numbered(pid, base_folder):
        return False
    return (
        pid.startswith(f"{base_folder}/category images/")
        or pid.startswith(f"{base_folder}/Category Images/")
        or (
            pid.startswith(f"{base_folder}/categories/")
            and not is_legacy_numbered(pid, base_folder)
        )
    )


async def run(dry_run: bool) -> None:
    settings = get_settings()
    base_folder = settings.cloudinary_folder
    asset_folder = f"{base_folder}/{TARGET_ASSET_FOLDER}"
    configure_cloudinary()

    all_ids = list_category_public_ids(base_folder)
    active = [pid for pid in all_ids if is_active_category_image(pid, base_folder)]
    legacy = [pid for pid in all_ids if is_legacy_numbered(pid, base_folder)]

    print(f"Base folder:        {base_folder}")
    print(f"Target asset folder:{asset_folder}")
    print(f"Active images:      {len(active)}")
    print(f"Legacy duplicates:  {len(legacy)}")
    if dry_run:
        print("Mode: DRY-RUN\n")

    if not dry_run:
        try:
            cloudinary.api.create_folder(asset_folder)
            print(f"Created folder: {asset_folder}")
        except Exception as exc:
            if "already exists" in str(exc).lower():
                print(f"Folder already exists: {asset_folder}")
            else:
                print(f"Folder create note: {exc}")

    moved = deleted = failed = 0

    for idx, pid in enumerate(active, 1):
        prefix = f"[move {idx}/{len(active)}] {pid.split('/')[-1]}"
        if dry_run:
            print(f"{prefix}  DRY-RUN -> {asset_folder}")
            moved += 1
            continue
        try:
            cloudinary.api.update(pid, asset_folder=asset_folder)
            print(f"{prefix}  OK")
            moved += 1
        except Exception as exc:
            print(f"{prefix}  FAIL — {exc}")
            failed += 1
        time.sleep(0.2)

    for idx, pid in enumerate(legacy, 1):
        prefix = f"[delete {idx}/{len(legacy)}] {pid.split('/')[-1]}"
        if dry_run:
            print(f"{prefix}  DRY-RUN delete legacy duplicate")
            deleted += 1
            continue
        try:
            cloudinary.uploader.destroy(pid, resource_type="image")
            print(f"{prefix}  deleted")
            deleted += 1
        except Exception as exc:
            print(f"{prefix}  FAIL — {exc}")
            failed += 1
        time.sleep(0.2)

    if not dry_run and legacy:
        try:
            cloudinary.api.delete_folder(f"{base_folder}/categories")
            print(f"Removed empty folder: {base_folder}/categories")
        except Exception as exc:
            print(f"Legacy categories folder note: {exc}")

    # Verify one asset
    if active and not dry_run:
        sample = active[0]
        meta = cloudinary.api.resource(sample, resource_type="image")
        print(f"\nVerify {sample.split('/')[-1]}:")
        print(f"  asset_folder = {meta.get('asset_folder')!r}")
        print(f"  url          = {meta.get('secure_url', '')[:90]}...")

    print(f"\n{'=' * 60}")
    print(f"DONE — moved: {moved}  deleted: {deleted}  failed: {failed}")
    if dry_run:
        print("(dry-run — no changes were written)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix category image Cloudinary folders")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.cloudinary_configured and not args.dry_run:
        raise SystemExit("ERROR: Cloudinary is not configured in .env")

    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
