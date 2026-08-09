"""
Upload product images from PRODUCT IMAGES/ subfolders to Cloudinary and update PostgreSQL.

Local layout:
  PRODUCT IMAGES/<Category_folder>/<product_id>_<product_name>.<ext>

Cloudinary layout:
  gms-world-foods/Product Images/<category_folder>/<product_id>

For each image:
  1. Upload to Cloudinary under the matching category folder
  2. Upsert product_images row (is_primary=true, display_order=0)

Run from project root:
    python scripts/uploads/upload_product_images.py

Flags:
    --dry-run           Preview without uploading or writing to DB
    --skip-existing     Skip products whose primary image URL is already under Product Images
    --categories NAMES  Comma-separated local folder names (default: all subfolders)
    --log-file PATH     Append progress log to file (default: scripts/upload_log.txt)
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

from app.config import get_settings
from app.core.cloudinary_storage import configure_cloudinary, upload_bytes

IMAGES_ROOT = ROOT / "PRODUCT IMAGES"
PRODUCT_IMAGES_FOLDER = "Product Images"
SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
CACHE_FILE = ROOT / "app" / "core" / ".cache_invalidated"


def log(msg: str, log_fp) -> None:
    print(msg, flush=True)
    if log_fp:
        log_fp.write(msg + "\n")
        log_fp.flush()


def parse_product_id(filename: str) -> str | None:
    stem = Path(filename).stem
    product_id = stem.split("_", 1)[0].strip()
    return product_id or None


def discover_category_folders(selected: set[str] | None) -> list[str]:
    if not IMAGES_ROOT.is_dir():
        raise SystemExit(f"ERROR: Folder not found: {IMAGES_ROOT}")

    folders = sorted(
        entry.name
        for entry in IMAGES_ROOT.iterdir()
        if entry.is_dir() and not entry.name.startswith(".")
    )
    if not folders:
        raise SystemExit(f"No category subfolders found in {IMAGES_ROOT}")

    if selected:
        missing = selected - set(folders)
        if missing:
            raise SystemExit(
                "Unknown category folder(s): "
                + ", ".join(sorted(missing))
                + f"\nAvailable: {', '.join(folders)}"
            )
        folders = [name for name in folders if name in selected]

    return folders


def collect_image_files(selected_folders: set[str] | None) -> list[tuple[str, str, Path]]:
    """Return (product_id, cloudinary_category_folder, image_path)."""
    items: list[tuple[str, str, Path]] = []

    for folder_name in discover_category_folders(selected_folders):
        folder = IMAGES_ROOT / folder_name
        for fpath in sorted(folder.iterdir()):
            if not fpath.is_file() or fpath.suffix.lower() not in SUPPORTED_EXTS:
                continue
            product_id = parse_product_id(fpath.name)
            if not product_id:
                print(f"  [WARN] Cannot parse product_id from: {fpath.name}")
                continue
            items.append((product_id, folder_name, fpath))

    return items


def cloudinary_paths(settings, category_folder: str, product_id: str) -> tuple[str, str]:
    """Return (target_folder, target_public_id)."""
    base = settings.cloudinary_folder
    target_folder = f"{base}/{PRODUCT_IMAGES_FOLDER}/{category_folder}"
    target_public_id = f"{target_folder}/{product_id}"
    return target_folder, target_public_id


def already_at_target(url: str, product_id: str) -> bool:
    if not url:
        return False
    normalized = url.lower().replace("%20", " ")
    return "product images" in normalized and product_id.lower() in normalized


def upload_to_cloudinary(
    *,
    product_id: str,
    category_folder: str,
    fpath: Path,
    settings,
) -> str:
    target_folder, _target_public_id = cloudinary_paths(settings, category_folder, product_id)
    data = fpath.read_bytes()
    ext = fpath.suffix.lower()
    result = upload_bytes(
        data,
        folder=target_folder,
        public_id=product_id,
        ext=ext,
    )
    return result["secure_url"]


async def connect_db(settings, ssl_ctx):
    import asyncpg

    return await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        ssl=ssl_ctx,
    )


async def ensure_db_conn(conn, settings, ssl_ctx):
    import asyncpg

    try:
        await conn.execute("SELECT 1")
        return conn
    except Exception:
        try:
            await conn.close()
        except Exception:
            pass
        return await connect_db(settings, ssl_ctx)


async def upsert_primary_image(conn, product_id: str, url: str) -> None:
    async with conn.transaction():
        await conn.execute(
            """
            UPDATE product_images
            SET is_primary = FALSE
            WHERE product_id = $1
            """,
            product_id,
        )
        existing_img = await conn.fetchrow(
            """
            SELECT id FROM product_images
            WHERE product_id = $1
            ORDER BY display_order ASC, id ASC
            LIMIT 1
            """,
            product_id,
        )
        if existing_img:
            await conn.execute(
                """
                UPDATE product_images
                SET image_url = $1,
                    is_primary = TRUE,
                    display_order = 0,
                    alt_text = $2
                WHERE id = $3
                """,
                url,
                product_id,
                existing_img["id"],
            )
        else:
            await conn.execute(
                """
                INSERT INTO product_images
                    (product_id, image_url, is_primary, display_order, alt_text)
                VALUES ($1, $2, TRUE, 0, $3)
                """,
                product_id,
                url,
                product_id,
            )


async def upload_and_update(
    items: list[tuple[str, str, Path]],
    *,
    dry_run: bool,
    skip_existing: bool,
    log_file: Path | None,
) -> None:
    import asyncpg
    import ssl as ssl_module

    settings = get_settings()
    log_fp = open(log_file, "a", encoding="utf-8") if log_file else None

    ssl_ctx = ssl_module.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl_module.CERT_NONE

    log(f"\nConnecting to PostgreSQL at {settings.db_host}:{settings.db_port}/{settings.db_name} …", log_fp)
    conn = await connect_db(settings, ssl_ctx)

    try:
        if not dry_run:
            configure_cloudinary()

        product_ids = [pid for pid, _, _ in items]
        log("Loading product and image metadata from DB …", log_fp)
        existing_products = {
            r["product_id"]
            for r in await conn.fetch(
                "SELECT product_id FROM products WHERE product_id = ANY($1::text[])",
                product_ids,
            )
        }
        primary_urls: dict[str, str] = {}
        if skip_existing:
            for r in await conn.fetch(
                """
                SELECT product_id, image_url
                FROM product_images
                WHERE product_id = ANY($1::text[]) AND is_primary = TRUE
                """,
                product_ids,
            ):
                primary_urls[r["product_id"]] = r["image_url"]

        total = len(items)
        ok = skipped = failed = 0
        log(f"Processing {total} image files …", log_fp)
        if dry_run:
            log("Mode: DRY-RUN\n", log_fp)

        for idx, (product_id, category_folder, fpath) in enumerate(items, 1):
            prefix = f"[{idx:>4}/{total}] {product_id} ({category_folder})"

            if product_id not in existing_products:
                log(f"{prefix}  SKIP — product not in database", log_fp)
                skipped += 1
                continue

            if skip_existing:
                current_url = primary_urls.get(product_id, "")
                if already_at_target(current_url, product_id):
                    skipped += 1
                    if idx % 100 == 0 or idx == total:
                        log(f"{prefix}  SKIP — already in Product Images  (skipped so far: {skipped})", log_fp)
                    continue

            if dry_run:
                ok += 1
                if idx % 250 == 0 or idx == total:
                    log(f"{prefix}  DRY-RUN progress — would upload {fpath.name}", log_fp)
                continue

            try:
                url = upload_to_cloudinary(
                    product_id=product_id,
                    category_folder=category_folder,
                    fpath=fpath,
                    settings=settings,
                )
            except Exception as exc:
                err = str(exc)
                log(f"{prefix}  FAIL upload — {err}", log_fp)
                failed += 1
                if "rate" in err.lower() or "420" in err or "429" in err:
                    time.sleep(5)
                else:
                    time.sleep(0.3)
                continue

            try:
                conn = await ensure_db_conn(conn, settings, ssl_ctx)
                await upsert_primary_image(conn, product_id, url)
                log(f"{prefix}  OK  — {url}", log_fp)
                ok += 1
                if ok % 50 == 0:
                    log(f"  … progress: {ok} uploaded, {failed} failed, {skipped} skipped", log_fp)
                    conn = await ensure_db_conn(conn, settings, ssl_ctx)
            except Exception as exc:
                log(f"{prefix}  FAIL db — {exc}", log_fp)
                failed += 1
                try:
                    conn = await connect_db(settings, ssl_ctx)
                except Exception as reconnect_exc:
                    log(f"{prefix}  FAIL reconnect — {reconnect_exc}", log_fp)

            if idx % 75 == 0:
                conn = await ensure_db_conn(conn, settings, ssl_ctx)

            time.sleep(0.2)

        if not dry_run and ok > 0:
            try:
                CACHE_FILE.touch()
            except OSError:
                pass

        log(f"\n{'=' * 60}", log_fp)
        log(f"DONE — OK: {ok}  |  Skipped: {skipped}  |  Failed: {failed}  |  Total: {total}", log_fp)
        if dry_run:
            log("(dry-run — no changes were written)", log_fp)

    finally:
        await conn.close()
        if log_fp:
            log_fp.close()


def resolve_selected_folders(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    selected = {part.strip() for part in raw.split(",") if part.strip()}
    return selected or None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload product images to Cloudinary Product Images/<category>/ and update DB"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip products whose primary image is already under Product Images",
    )
    parser.add_argument(
        "--categories",
        default=None,
        metavar="NAMES",
        help="Comma-separated local folder names or category slugs (default: all 9)",
    )
    parser.add_argument(
        "--log-file",
        default=str(ROOT / "scripts" / "upload_log.txt"),
        help="Log file path",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.cloudinary_configured and not args.dry_run:
        raise SystemExit("ERROR: Cloudinary is not configured. Set CLOUDINARY_* in .env")

    selected = resolve_selected_folders(args.categories)
    items = collect_image_files(selected)
    if not items:
        raise SystemExit("No image files found for the selected categories.")

    by_folder: dict[str, int] = {}
    for _, folder_name, _ in items:
        by_folder[folder_name] = by_folder.get(folder_name, 0) + 1

    print(f"Source: {IMAGES_ROOT}")
    print(f"Found {len(items)} image files:")
    for folder_name, count in sorted(by_folder.items()):
        print(f"  {folder_name:<35} {count:>4} files")
    print(f"\nCloudinary target: {settings.cloudinary_folder}/Product Images/<category>/<product_id>")

    asyncio.run(
        upload_and_update(
            items,
            dry_run=args.dry_run,
            skip_existing=args.skip_existing,
            log_file=Path(args.log_file) if args.log_file else None,
        )
    )


if __name__ == "__main__":
    main()
