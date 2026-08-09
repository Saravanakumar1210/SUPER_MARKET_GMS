"""Check whether the DB still has old flat URLs for the first batch that Cloudinary already renamed."""

import asyncio
import asyncpg
import ssl
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.config import get_settings

SAMPLE_IDS = [
    'DGS01-LD02-P0001', 'DGS01-LD02-P0002', 'DGS01-LD02-P0003',
    'DGS01-ND07-P0001', 'HPC08-DP06-P0006', 'FRP04-EV04-P0001',
]

async def main():
    s = get_settings()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    conn = await asyncpg.connect(
        host=s.db_host, port=s.db_port, database=s.db_name,
        user=s.db_user, password=s.db_password, ssl=ctx
    )
    rows = await conn.fetch(
        "SELECT product_id, image_url FROM product_images WHERE product_id = ANY($1::text[])",
        SAMPLE_IDS,
    )
    for r in rows:
        print(f"{r['product_id']}: {r['image_url']}")
    await conn.close()

asyncio.run(main())
