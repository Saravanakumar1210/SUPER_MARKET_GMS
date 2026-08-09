"""Seed products.kitchen_culture from curated product name lists."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import asyncio

from sqlalchemy import select

from app.core.catalog import invalidate_catalog_cache
from app.core.db_indexes import ensure_performance_indexes
from app.core.kitchen_cultures import (
    KITCHEN_CULTURE_SEED_QUERIES,
    KITCHEN_CULTURES,
    product_matches_query,
)
from app.database import AsyncSessionLocal
from app.models import Product


async def main(force: bool = False) -> None:
    async with AsyncSessionLocal() as db:
        await ensure_performance_indexes(db)
        result = await db.execute(select(Product))
        products = list(result.scalars().all())

        assigned = 0
        for culture in KITCHEN_CULTURES:
            key = culture["key"]
            queries = KITCHEN_CULTURE_SEED_QUERIES.get(key, [])
            for product in products:
                if product.kitchen_culture and not force:
                    continue
                for query in queries:
                    if product_matches_query(product.product_name, query):
                        product.kitchen_culture = key
                        assigned += 1
                        break

        await db.commit()

    invalidate_catalog_cache()
    print(f"Kitchen culture seed complete — {assigned} product assignment(s).")
    for culture in KITCHEN_CULTURES:
        key = culture["key"]
        async with AsyncSessionLocal() as db:
            count = (
                await db.execute(
                    select(Product).where(Product.kitchen_culture == key, Product.is_active)
                )
            ).scalars().all()
        print(f"  {culture['label']}: {len(count)} active products")


if __name__ == "__main__":
    import sys

    force_flag = "--force" in sys.argv
    asyncio.run(main(force=force_flag))
