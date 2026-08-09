"""Print kitchen_culture assignment counts from the database."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import asyncio

from sqlalchemy import text

from app.database import AsyncSessionLocal


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                "SELECT kitchen_culture, COUNT(*) c FROM products "
                "WHERE kitchen_culture IS NOT NULL "
                "GROUP BY kitchen_culture ORDER BY c DESC"
            )
        )
        for row in result.fetchall():
            print(f"{row[0]}: {row[1]}")

        total = await db.execute(
            text("SELECT COUNT(*) FROM products WHERE kitchen_culture IS NOT NULL")
        )
        print(f"\nTotal with culture: {total.scalar_one()}")

        sample = await db.execute(
            text(
                "SELECT product_name, kitchen_culture FROM products "
                "WHERE product_name ILIKE '%nongshim%' LIMIT 5"
            )
        )
        print("\nNongshim products:")
        for row in sample.fetchall():
            print(f"  {row[0]} -> {row[1]!r}")


if __name__ == "__main__":
    asyncio.run(main())
