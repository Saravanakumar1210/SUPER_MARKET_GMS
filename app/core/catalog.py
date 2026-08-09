import time
from pathlib import Path
from typing import Any

from sqlalchemy import Select, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Category, Product, ProductImage, Subcategory

HIDDEN_CATEGORIES = {"oyster", "lottery", "vape", "lottery payout", "paypoint"}

# ---------------------------------------------------------------------------
# TTL in-memory cache with cross-process invalidation via a shared file flag.
#
# A single site process serves all users. The invalidation file still matters
# when multiple workers/processes share the same codebase (or after restarts):
# invalidate_catalog_cache() writes a wall-clock timestamp so every process
# treats older in-memory entries as stale.
# ---------------------------------------------------------------------------
_CACHE_TTL = 1800  # 30 minutes max TTL regardless of invalidation file
_CACHE_MAX_ENTRIES = 500  # prevent unbounded growth from unique admin query keys
_cache: dict[str, tuple[float, Any]] = {}

# Shared invalidation flag file — writable by all site processes
_INVALIDATION_FILE = Path(__file__).parent / ".cache_invalidated"


def _invalidation_time() -> float:
    """Return the mtime of the invalidation file, or 0.0 if it doesn't exist."""
    try:
        return _INVALIDATION_FILE.stat().st_mtime
    except OSError:
        return 0.0


def _cache_get(key: str) -> Any | None:
    entry = _cache.get(key)
    if not entry:
        return None
    store_wall, value = entry[0], entry[1]
    # Expired by TTL?
    if time.time() - store_wall >= _CACHE_TTL:
        return None
    # Invalidated by another process (e.g. admin server)?
    if _invalidation_time() > store_wall:
        return None
    return value


def _cache_set(key: str, value: Any) -> None:
    # Evict the oldest quarter of entries when the cache is full.
    if len(_cache) >= _CACHE_MAX_ENTRIES:
        sorted_keys = sorted(_cache, key=lambda k: _cache[k][0])
        for old_key in sorted_keys[: _CACHE_MAX_ENTRIES // 4]:
            _cache.pop(old_key, None)
    # Store wall-clock time so cross-process mtime comparison works correctly.
    _cache[key] = (time.time(), value)


def invalidate_catalog_cache() -> None:
    """Clear this process's cache AND signal all other server processes."""
    _cache.clear()
    # Touch the shared file so other processes detect the invalidation.
    try:
        _INVALIDATION_FILE.touch()
    except OSError:
        pass


def admin_cache_get(key: str) -> Any | None:
    return _cache_get(f"admin:{key}")


def admin_cache_set(key: str, value: Any) -> None:
    _cache_set(f"admin:{key}", value)


def admin_cache_invalidate(*keys: str) -> None:
    for key in keys:
        _cache.pop(f"admin:{key}", None)


def invalidate_admin_site_cache(*admin_keys: str) -> None:
    """Invalidate admin list caches and broadcast to all server workers."""
    if admin_keys:
        admin_cache_invalidate(*admin_keys)
    invalidate_catalog_cache()


def product_to_dict(p: Product, primary_image: str | None = None) -> dict[str, Any]:
    return {
        "productId": p.product_id,
        "categoryId": p.category_id,
        "categoryName": p.category.category_name if p.category else "",
        "subCategoryId": p.subcategory_id,
        "subCategoryName": p.subcategory.subcategory_name if p.subcategory else "",
        "productName": p.product_name,
        "displayName": p.product_name,
        "weightKG": float(p.weight_kg) if p.weight_kg is not None else None,
        "packType": p.unit_label or "",
        "unitLabel": p.unit_label or "",
        "locationId": 52,
        "salesUnitTypeId": 1,
        "flaggedCategoryMismatch": False,
        "productDescription": p.description or "",
        "primaryImageUrl": primary_image,
        "isFeatured": bool(p.is_featured),
        "isBestSeller": bool(p.is_best_seller),
        "isNewArrival": bool(p.is_new_arrival),
        "isHotOffer": bool(p.is_hot_offer),
        "isExclusive": bool(p.is_exclusive),
        "discountPercent": int(p.discount_percent or 0),
        "kitchenCulture": p.kitchen_culture,
    }


def admin_product_to_dict(p: Product, primary_image: str | None = None) -> dict[str, Any]:
    base = product_to_dict(p, primary_image)
    base.update(
        {
            "brand": p.brand or "",
            "slug": p.slug,
            "sellingPrice": float(p.selling_price),
            "comparePrice": float(p.compare_price) if p.compare_price is not None else None,
            "discountPercent": int(p.discount_percent or 0),
            "stockQuantity": int(p.stock_quantity or 0),
            "minOrderQty": int(p.min_order_qty or 1),
            "isWholesale": bool(p.is_wholesale),
            "isActive": bool(p.is_active),
            "kitchenCulture": p.kitchen_culture,
            "images": [
                {
                    "id": img.id,
                    "imageUrl": img.image_url,
                    "isPrimary": bool(img.is_primary),
                    "displayOrder": int(img.display_order or 0),
                    "altText": img.alt_text or "",
                }
                for img in sorted(
                    p.images or [],
                    key=lambda i: (not i.is_primary, i.display_order, i.id),
                )
            ],
        }
    )
    return base


def admin_product_row_to_dict(row: Any) -> dict[str, Any]:
    """Slim serialiser for admin paginated list rows (raw SQL, no ORM images).

    Mirrors the fields produced by ``admin_product_to_dict`` but works on the
    lightweight SQL row returned by ``_fetch_admin_products_page`` — it sets
    ``images`` to an empty list because the list view only needs the primary
    image URL, which is included as ``primaryImageUrl``.
    """
    price = float(row.selling_price)
    return {
        "productId": row.product_id,
        "categoryId": row.category_id,
        "categoryName": row.category_name or "",
        "subCategoryId": row.subcategory_id,
        "subCategoryName": row.subcategory_name or "",
        "productName": row.product_name,
        "displayName": row.product_name,
        "brand": row.brand or "",
        "slug": row.slug,
        "sellingPrice": price,
        "comparePrice": float(row.compare_price) if row.compare_price is not None else None,
        "discountPercent": int(row.discount_percent or 0),
        "stockQuantity": int(row.stock_quantity or 0),
        "minOrderQty": int(row.min_order_qty or 1),
        "isWholesale": bool(row.is_wholesale),
        "isActive": bool(row.is_active),
        "isFeatured": bool(row.is_featured),
        "isBestSeller": bool(row.is_best_seller),
        "isNewArrival": bool(row.is_new_arrival),
        "isHotOffer": bool(row.is_hot_offer),
        "isExclusive": bool(row.is_exclusive),
        "kitchenCulture": row.kitchen_culture or "",
        "primaryImageUrl": row.primary_image_url,
        "images": [],
    }


async def get_category_stats(db: AsyncSession) -> list[dict]:
    cached = _cache_get("category_stats")
    if cached is not None:
        return cached

    # Single query: aggregates + median via PERCENTILE_CONT (PostgreSQL)
    result = await db.execute(text("""
        SELECT
            c.category_id,
            c.category_name,
            c.icon_image_url,
            c.banner_image_url,
            COUNT(p.product_id)                                               AS cnt,
            MIN(p.selling_price)                                              AS min_price,
            MAX(p.selling_price)                                              AS max_price,
            AVG(p.selling_price)                                              AS avg_price,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.selling_price)     AS median_price,
            c.display_order
        FROM categories c
        JOIN products p ON p.category_id = c.category_id
        WHERE c.is_active = true AND p.is_active = true
        GROUP BY c.category_id, c.category_name, c.icon_image_url,
                 c.banner_image_url, c.display_order
        ORDER BY c.display_order, c.category_name
    """))

    stats = []
    for row in result.fetchall():
        if row.category_name.lower() in HIDDEN_CATEGORIES:
            continue
        stats.append({
            "ProductCategoryID": row.category_id,
            "CategoryName": row.category_name,
            "IconImageUrl": row.icon_image_url or "",
            "BannerImageUrl": row.banner_image_url or row.icon_image_url or "",
            "Product_Count": row.cnt,
            "Min_Price": float(row.min_price or 0),
            "Max_Price": float(row.max_price or 0),
            "Avg_Price": round(float(row.avg_price or 0), 2),
            "Median_Price": round(float(row.median_price or 0), 2),
        })

    _cache_set("category_stats", stats)
    return stats


async def get_subcategory_stats(db: AsyncSession, category_id: str | None = None) -> list[dict]:
    cache_key = f"subcategory_stats:{category_id or 'all'}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    where_clause = "AND s.category_id = :cat_id" if category_id else ""
    result = await db.execute(text(f"""
        SELECT
            s.subcategory_id,
            s.category_id,
            c.category_name,
            s.subcategory_name,
            COUNT(p.product_id)                                               AS cnt,
            MIN(p.selling_price)                                              AS min_price,
            MAX(p.selling_price)                                              AS max_price,
            AVG(p.selling_price)                                              AS avg_price,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.selling_price)     AS median_price
        FROM subcategories s
        JOIN categories c ON c.category_id = s.category_id
        JOIN products p ON p.subcategory_id = s.subcategory_id
        WHERE s.is_active = true AND p.is_active = true {where_clause}
        GROUP BY s.subcategory_id, s.category_id, c.category_name,
                 s.subcategory_name, s.display_order
        ORDER BY s.display_order
    """), {"cat_id": category_id} if category_id else {})

    stats = []
    for row in result.fetchall():
        if row.category_name.lower() in HIDDEN_CATEGORIES:
            continue
        stats.append({
            "ProductCategoryID": row.category_id,
            "CategoryName": row.category_name,
            "ProductSubCategoryID": row.subcategory_id,
            "SubCategoryName": row.subcategory_name,
            "Product_Count": row.cnt,
            "Min_Price": float(row.min_price or 0),
            "Max_Price": float(row.max_price or 0),
            "Avg_Price": round(float(row.avg_price or 0), 2),
            "Median_Price": round(float(row.median_price or 0), 2),
        })

    _cache_set(cache_key, stats)
    return stats


def build_products_query(
    *,
    category: str | None = None,
    subcategory: str | None = None,
    pack_type: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    search: str | None = None,
    sort_by: str = "name-asc",
    flag: str | None = None,
) -> Select:
    q = (
        select(Product)
        .options(
            selectinload(Product.category),
            selectinload(Product.subcategory),
            selectinload(Product.images),
        )
        .where(Product.is_active.is_(True))
    )
    if category:
        q = q.join(Category).where(
            or_(Category.category_id == category, Category.category_name.ilike(category))
        )
    if subcategory:
        if not category:
            q = q.join(Subcategory, Product.subcategory_id == Subcategory.subcategory_id)
        else:
            q = q.join(Subcategory, Product.subcategory_id == Subcategory.subcategory_id, isouter=True)
        q = q.where(
            or_(
                Subcategory.subcategory_id == subcategory,
                Subcategory.subcategory_name.ilike(subcategory),
            )
        )
    if pack_type:
        if pack_type.lower() == "not specified":
            q = q.where(or_(Product.unit_label == "", Product.unit_label.is_(None)))
        else:
            q = q.where(Product.unit_label.ilike(pack_type))
    if min_price is not None:
        q = q.where(Product.selling_price >= min_price)
    if max_price is not None:
        q = q.where(Product.selling_price <= max_price)
    if search:
        term = f"%{search.strip()}%"
        q = q.where(
            or_(
                Product.product_name.ilike(term),
                Product.description.ilike(term),
            )
        )
    flag_map = {
        "featured": Product.is_featured,
        "best-sellers": Product.is_best_seller,
        "new-arrivals": Product.is_new_arrival,
        "hot-offers": Product.is_hot_offer,
        "exclusive": Product.is_exclusive,
    }
    if flag and flag in flag_map:
        q = q.where(flag_map[flag].is_(True))

    sort_map = {
        "name-asc": Product.product_name.asc(),
        "name-desc": Product.product_name.desc(),
        "price-asc": Product.selling_price.asc(),
        "price-desc": Product.selling_price.desc(),
    }
    q = q.order_by(sort_map.get(sort_by, Product.product_name.asc()))
    return q


def primary_image(product: Product) -> str | None:
    for img in product.images:
        if img.is_primary:
            return img.image_url
    return product.images[0].image_url if product.images else None
