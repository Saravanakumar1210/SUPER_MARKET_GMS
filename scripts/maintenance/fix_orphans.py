"""
Fix the 8 orphan DB rows that have Cloudinary URLs pointing to non-existent assets.
These rows reference product_ids that don't have any actual image on Cloudinary.
We simply NULL out / delete these rows so products show the placeholder in UI.
"""
import asyncio
import asyncpg
import ssl
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.config import get_settings

ORPHAN_PRODUCT_IDS = [
    "DGS01-RR01-P0007",
    "DGS01-RR01-P0008",
    "DGS01-RR01-P0014",
    "DGS01-RR01-P0015",
    "DGS01-SP03-P0026",
    "DGS01-SP03-P0029",
    "FMR05-FM01-P0008",
    "HPC08-DP06-P0006",
]

async def fix():
    s = get_settings()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    conn = await asyncpg.connect(
        host=s.db_host, port=s.db_port,
        database=s.db_name, user=s.db_user, password=s.db_password,
        ssl=ctx
    )
    print("Checking orphan image rows...")
    for pid in ORPHAN_PRODUCT_IDS:
        rows = await conn.fetch(
            "SELECT id, image_url FROM product_images WHERE product_id = $1", pid
        )
        for r in rows:
            print(f"  {pid}: {r['image_url'][:80]}")
            # Delete the orphan row — product will show placeholder until a real image is added
            await conn.execute("DELETE FROM product_images WHERE id = $1", r['id'])
            print(f"    -> DELETED image row id={r['id']}")

    # Touch cache invalidation file
    from pathlib import Path
    inv = Path('app/core/.cache_invalidated')
    inv.touch()
    print("\nCache invalidated. Done.")
    await conn.close()

asyncio.run(fix())
