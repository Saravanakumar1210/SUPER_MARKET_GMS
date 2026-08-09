"""
Clear all product discounts directly via the database.
Run: python scripts/maintenance/clear_discounts.py
"""
import asyncio
import ssl
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import asyncpg
from app.config import get_settings


async def main() -> None:
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

    # Check how many products currently have discounts
    before = await conn.fetchval(
        "SELECT COUNT(*) FROM products WHERE discount_percent > 0"
    )
    print(f"Products with discounts before: {before}")

    if before == 0:
        print("No discounts to clear.")
        await conn.close()
        return

    # Restore original price where compare_price exists, then zero out discount fields
    updated = await conn.execute(
        """
        UPDATE products
        SET
            selling_price    = COALESCE(compare_price, selling_price),
            compare_price    = NULL,
            discount_percent = 0,
            is_hot_offer     = FALSE
        WHERE discount_percent > 0
        """
    )
    print(f"Updated: {updated}")

    after = await conn.fetchval(
        "SELECT COUNT(*) FROM products WHERE discount_percent > 0"
    )
    print(f"Products with discounts after:  {after}")

    await conn.close()
    print("Done. Restart the server (or wait 30 min) for the cache to clear.")


asyncio.run(main())
