"""Quick status check for product image upload progress."""
import asyncio
import ssl
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.config import get_settings

IMAGES_ROOT = ROOT / "IMAGES"


async def main() -> None:
    import asyncpg

    s = get_settings()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    conn = await asyncpg.connect(
        host=s.db_host,
        port=s.db_port,
        database=s.db_name,
        user=s.db_user,
        password=s.db_password,
        ssl=ctx,
    )

    print("=== Images by URL pattern ===")
    rows = await conn.fetch(
        """
        SELECT
            CASE
                WHEN image_url ILIKE '%Product%Images%' THEN 'Product Images folder'
                WHEN image_url LIKE '%/products/%/%' THEN 'products/category subfolder'
                WHEN image_url LIKE '%/products/%' THEN 'products flat'
                ELSE 'other'
            END AS pattern,
            COUNT(*) AS cnt
        FROM product_images
        WHERE is_primary = TRUE
        GROUP BY 1
        ORDER BY 2 DESC
        """
    )
    for r in rows:
        print(f"  {r['pattern']}: {r['cnt']}")

    print("\n=== Primary images per category (DB) ===")
    rows2 = await conn.fetch(
        """
        SELECT c.slug, c.category_name, COUNT(pi.id) AS img_count
        FROM categories c
        LEFT JOIN products p ON p.category_id = c.category_id
        LEFT JOIN product_images pi ON pi.product_id = p.product_id AND pi.is_primary = TRUE
        GROUP BY c.slug, c.category_name
        ORDER BY c.slug
        """
    )
    for r in rows2:
        print(f"  {r['slug']:<35} {r['img_count']:>4} images  ({r['category_name']})")

    print("\n=== Local IMAGES folder file counts ===")
    exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    for folder in sorted(IMAGES_ROOT.iterdir()):
        if not folder.is_dir():
            continue
        count = sum(1 for f in folder.iterdir() if f.suffix.lower() in exts)
        print(f"  {folder.name:<35} {count:>4} files")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
