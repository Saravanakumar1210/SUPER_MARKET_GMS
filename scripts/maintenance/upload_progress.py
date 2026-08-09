import asyncio
import ssl
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.config import get_settings

TARGETS = {
    "bakery-pasta-noodles": ("Bakery, Pasta & Noodles", 133),
    "beverages": ("Beverages", 214),
    "condiments-sauces-pickles": ("Condiments, Sauces & Pickles", 161),
    "dairy-eggs-chilled": ("Dairy, Eggs & Chilled", 103),
    "dry-grocery-staples": ("Dry Grocery & Staples", 1962),
    "fresh-produce": ("Fresh Produce", 784),
    "frozen-meat-ready-to-cook": ("Frozen, Meat & Ready-to-Cook", 223),
    "household-personal-care": ("Household & Personal Care", 300),
    "snacks-confectionery": ("Snacks & Confectionery", 472),
}


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
    rows = await conn.fetch(
        """
        SELECT c.slug, COUNT(pi.id) AS cnt
        FROM categories c
        LEFT JOIN products p ON p.category_id = c.category_id
        LEFT JOIN product_images pi
          ON pi.product_id = p.product_id
         AND pi.is_primary = TRUE
         AND pi.image_url ILIKE '%Product%Images%'
        GROUP BY c.slug
        ORDER BY c.slug
        """
    )
    total = await conn.fetchval(
        """
        SELECT COUNT(*) FROM product_images
        WHERE is_primary = TRUE AND image_url ILIKE '%Product%Images%'
        """
    )
    await conn.close()

    print(f"TOTAL|{total}|4352")
    for r in rows:
        slug = r["slug"]
        name, target = TARGETS.get(slug, (slug, 0))
        print(f"{name}|{r['cnt']}|{target}")


if __name__ == "__main__":
    asyncio.run(main())
