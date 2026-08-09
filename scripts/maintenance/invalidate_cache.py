"""Touch the cache invalidation file so the live server drops stale data instantly."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.core.catalog import invalidate_catalog_cache
invalidate_catalog_cache()
print("Cache invalidated.")
