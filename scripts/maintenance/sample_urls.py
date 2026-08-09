import asyncio
import ssl
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.config import get_settings


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

    print("=== Sample other URLs ===")
    rows = await conn.fetch(
        """
        SELECT product_id, image_url FROM product_images
        WHERE is_primary = TRUE
          AND image_url NOT LIKE '%/products/%'
        LIMIT 8
        """
    )
    for r in rows:
        print(f"  {r['product_id']}: {r['image_url'][:140]}")

    print("\n=== Sample dry-grocery URLs ===")
    rows2 = await conn.fetch(
        """
        SELECT pi.product_id, pi.image_url
        FROM product_images pi
        JOIN products p ON p.product_id = pi.product_id
        JOIN categories c ON c.category_id = p.category_id
        WHERE c.slug = 'dry-grocery-staples' AND pi.is_primary = TRUE
        LIMIT 5
        """
    )
    for r in rows2:
        print(f"  {r['product_id']}: {r['image_url'][:140]}")

    print("\n=== Per category: cloudinary in products/ vs other ===")
    rows3 = await conn.fetch(
        """
        SELECT c.slug,
            SUM(CASE WHEN pi.image_url LIKE '%cloudinary.com%products/%' THEN 1 ELSE 0 END) AS in_products,
            SUM(CASE WHEN pi.image_url LIKE '%cloudinary.com%' AND pi.image_url NOT LIKE '%/products/%' THEN 1 ELSE 0 END) AS cloudinary_other,
            SUM(CASE WHEN pi.image_url NOT LIKE '%cloudinary.com%' THEN 1 ELSE 0 END) AS non_cloudinary
        FROM categories c
        JOIN products p ON p.category_id = c.category_id
        JOIN product_images pi ON pi.product_id = p.product_id AND pi.is_primary = TRUE
        GROUP BY c.slug ORDER BY c.slug
        """
    )
    for r in rows3:
        print(
            f"  {r['slug']:<35} products={r['in_products']:>4}  "
            f"cloudinary_other={r['cloudinary_other']:>4}  non_cloudinary={r['non_cloudinary']:>4}"
        )

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
