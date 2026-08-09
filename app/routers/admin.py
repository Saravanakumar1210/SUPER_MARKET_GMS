import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.config import get_settings
from app.core.banner_order import (
    append_to_tail,
    ensure_banner_chains,
    insert_at_index,
    load_all_banners,
    move_banner as move_banner_in_chain,
    relocate_on_active_change,
    serialize_banners,
    unlink_banner,
)
from app.core.culture_order import (
    append_to_tail as append_culture_to_tail,
    ensure_culture_chains,
    insert_at_index as insert_culture_at_index,
    load_all_cultures,
    move_culture,
    relocate_on_active_change as relocate_culture_on_active_change,
    serialize_cultures,
    unlink_culture,
)
from app.core.kitchen_cultures import KITCHEN_CULTURES, normalize_kitchen_culture
from app.core.site_settings import SITE_SETTING_KEYS, load_public_site_settings
from app.core.catalog import (
    admin_cache_get,
    admin_cache_set,
    admin_product_to_dict,
    admin_product_row_to_dict,
    invalidate_admin_site_cache,
    invalidate_catalog_cache,
    primary_image,
)
from app.core.helpers import require_admin
from app.database import get_db
from app.models import Category, CultureBanner, Product, ProductImage, SiteBanner, SiteSetting, Subcategory, Testimonial, User
from app.models.site import ContactSubmission
from app.core.cloudinary_storage import delete_by_url, upload_upload_file
from app.paths import PRODUCT_UPLOADS_DIR
from app.schemas import (
    AdminBulkDiscountIn,
    AdminBulkProductActionIn,
    AdminCategoryIn,
    AdminClearDiscountsIn,
    AdminProductImageIn,
    AdminProductIn,
    AdminStatsOut,
    AdminSubcategoryIn,
    CouponOut,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_BANNER_BYTES = 12 * 1024 * 1024


def _payload(body) -> dict:
    return body.model_dump(exclude_unset=True) if hasattr(body, "model_dump") else dict(body or {})


def _admin_products_cache_key(
    *,
    page: int,
    per_page: int,
    category_id: str | None,
    subcategory_id: str | None,
    search: str | None,
    stock: str | None,
    kitchen_culture: str | None,
    sort: str,
    active_filter: str,
) -> str:
    return (
        f"products:{page}:{per_page}:{category_id}:{subcategory_id}:"
        f"{search}:{stock}:{kitchen_culture}:{sort}:{active_filter}"
    )


async def _fetch_admin_products_page(
    db: AsyncSession,
    *,
    page: int,
    per_page: int,
    category_id: str | None,
    subcategory_id: str | None,
    search: str | None,
    stock: str | None,
    kitchen_culture: str | None = None,
    sort: str | None = None,
    active_filter: str = "active",
) -> dict:
    from sqlalchemy import text as _text

    where: list[str] = []
    if active_filter == "inactive":
        where.append("p.is_active = false")
    elif active_filter != "all":
        where.append("p.is_active = true")
    params: dict = {"offset": (page - 1) * per_page, "limit": per_page}

    if category_id:
        where.append("p.category_id = :category_id")
        params["category_id"] = category_id
    if subcategory_id:
        where.append("p.subcategory_id = :subcategory_id")
        params["subcategory_id"] = subcategory_id
    if search:
        term = search.strip()
        if term:
            where.append(
                "(p.product_name ILIKE :search OR p.brand ILIKE :search OR p.product_id ILIKE :search)"
            )
            params["search"] = f"%{term}%"
    if stock == "in":
        where.append("p.stock_quantity >= 20")
    elif stock == "low":
        where.append("p.stock_quantity BETWEEN 1 AND 19")
    elif stock == "out":
        where.append("p.stock_quantity <= 0")
    if kitchen_culture:
        where.append("p.kitchen_culture = :kitchen_culture")
        params["kitchen_culture"] = kitchen_culture.strip().lower()

    where_sql = " AND ".join(where) if where else "1=1"
    has_filters = bool(
        search or category_id or subcategory_id or stock or kitchen_culture or active_filter != "active"
    )

    if sort == "name_desc":
        order_sql = "p.product_name DESC"
    elif sort == "name_asc":
        order_sql = "p.product_name ASC"
    elif sort == "category_desc":
        order_sql = "c.category_name DESC, p.product_name ASC"
    elif sort == "category_asc":
        order_sql = "c.category_name ASC, p.product_name ASC"
    elif sort == "discount_desc":
        order_sql = "p.discount_percent DESC NULLS LAST, p.product_name ASC"
    elif sort == "discount_asc":
        order_sql = "p.discount_percent ASC NULLS LAST, p.product_name ASC"
    elif sort == "stock_desc":
        order_sql = "p.stock_quantity DESC, p.product_name ASC"
    elif sort == "stock_asc":
        order_sql = "p.stock_quantity ASC, p.product_name ASC"
    else:
        order_sql = "p.product_id ASC"

    if not has_filters:
        stats_cached = admin_cache_get("stats")
        if stats_cached is not None:
            total = int(stats_cached.total_products)
        else:
            total = (
                await db.execute(_text(f"SELECT COUNT(*) FROM products p WHERE {where_sql}"), params)
            ).scalar_one()
    elif search:
        total = (
            await db.execute(
                _text(f"""
                    SELECT COUNT(*)::int FROM (
                        SELECT 1 FROM products p WHERE {where_sql} LIMIT 501
                    ) _sub
                """),
                params,
            )
        ).scalar_one()
    else:
        total = (
            await db.execute(_text(f"SELECT COUNT(*) FROM products p WHERE {where_sql}"), params)
        ).scalar_one()

    rows = (
        await db.execute(
            _text(f"""
                SELECT
                    p.product_id,
                    p.product_name,
                    p.brand,
                    p.slug,
                    p.category_id,
                    p.subcategory_id,
                    p.selling_price,
                    p.compare_price,
                    p.discount_percent,
                    p.stock_quantity,
                    p.min_order_qty,
                    p.is_active,
                    p.is_featured,
                    p.is_best_seller,
                    p.is_new_arrival,
                    p.is_hot_offer,
                    p.is_exclusive,
                    p.is_wholesale,
                    p.kitchen_culture,
                    c.category_name,
                    COALESCE(s.subcategory_name, '') AS subcategory_name,
                    pi.image_url AS primary_image_url
                FROM products p
                JOIN categories c ON c.category_id = p.category_id
                LEFT JOIN subcategories s ON s.subcategory_id = p.subcategory_id
                LEFT JOIN LATERAL (
                    SELECT image_url
                    FROM product_images
                    WHERE product_id = p.product_id
                    ORDER BY is_primary DESC, display_order ASC, id ASC
                    LIMIT 1
                ) pi ON true
                WHERE {where_sql}
                ORDER BY {order_sql}
                OFFSET :offset LIMIT :limit
            """),
            params,
        )
    ).fetchall()

    count_capped = bool(search and total >= 501)
    if count_capped:
        total = 500

    return {
        "items": [admin_product_row_to_dict(r) for r in rows],
        "total_count": total,
        "total_pages": max(1, (total + per_page - 1) // per_page),
        "current_page": page,
        "per_page": per_page,
        "count_capped": count_capped,
    }


async def _fetch_admin_spotlight(db: AsyncSession) -> dict:
    from sqlalchemy import text as _text

    counts_row = (
        await db.execute(
            _text("""
                SELECT
                    COUNT(*) FILTER (WHERE is_featured    AND is_active) AS featured,
                    COUNT(*) FILTER (WHERE is_best_seller AND is_active) AS best_sellers,
                    COUNT(*) FILTER (WHERE is_new_arrival AND is_active) AS new_arrivals,
                    COUNT(*) FILTER (WHERE is_hot_offer   AND is_active) AS hot_offers,
                    COUNT(*) FILTER (WHERE is_exclusive   AND is_active) AS exclusive
                FROM products
            """)
        )
    ).fetchone()

    product_rows = (
        await db.execute(
            _text("""
                SELECT
                    p.product_id,
                    p.product_name,
                    p.is_featured,
                    p.is_best_seller,
                    p.is_new_arrival,
                    p.is_hot_offer,
                    p.is_exclusive,
                    c.category_name,
                    COALESCE(s.subcategory_name, '') AS subcategory_name,
                    pi.image_url AS primary_image_url
                FROM products p
                JOIN categories c ON c.category_id = p.category_id
                LEFT JOIN subcategories s ON s.subcategory_id = p.subcategory_id
                LEFT JOIN LATERAL (
                    SELECT image_url
                    FROM product_images
                    WHERE product_id = p.product_id
                    ORDER BY is_primary DESC, display_order ASC, id ASC
                    LIMIT 1
                ) pi ON true
                WHERE p.is_active = true
                  AND (
                    p.is_featured OR p.is_best_seller OR p.is_new_arrival
                    OR p.is_hot_offer OR p.is_exclusive
                  )
                ORDER BY p.product_name
                LIMIT 1000
            """)
        )
    ).fetchall()

    sections = {
        "featured": [],
        "bestSellers": [],
        "newArrivals": [],
        "hotOffers": [],
        "exclusive": [],
    }
    flag_map = (
        ("featured", "is_featured"),
        ("bestSellers", "is_best_seller"),
        ("newArrivals", "is_new_arrival"),
        ("hotOffers", "is_hot_offer"),
        ("exclusive", "is_exclusive"),
    )
    for row in product_rows:
        item = {
            "productId": row.product_id,
            "productName": row.product_name,
            "categoryName": row.category_name or "",
            "subCategoryName": row.subcategory_name or "",
            "primaryImageUrl": row.primary_image_url,
        }
        for section_key, col in flag_map:
            if getattr(row, col):
                sections[section_key].append(item)

    testimonial_rows = (
        await db.execute(
            select(Testimonial)
            .where(Testimonial.is_featured.is_(True))
            .order_by(Testimonial.display_order, Testimonial.id)
            .limit(200)
        )
    ).scalars().all()
    testimonials = [
        {
            "id": t.id,
            "customerName": t.customer_name,
            "customerInitial": t.customer_initial,
            "rating": t.rating,
            "quote": t.quote,
            "displayOrder": t.display_order,
            "isFeatured": t.is_featured,
        }
        for t in testimonial_rows
    ]

    counts = {
        "featured": counts_row.featured,
        "bestSellers": counts_row.best_sellers,
        "newArrivals": counts_row.new_arrivals,
        "hotOffers": counts_row.hot_offers,
        "exclusive": counts_row.exclusive,
        "testimonials": len(testimonials),
    }
    return {"counts": counts, "sections": sections, "testimonials": testimonials}


async def warm_admin_cache(db: AsyncSession) -> None:
    """Pre-load hot admin endpoints into the in-memory cache."""
    from sqlalchemy import text as _text

    row = (await db.execute(_text("""
        SELECT
            (SELECT COUNT(*) FROM products WHERE is_active)              AS total_products,
            (SELECT COUNT(*) FROM categories WHERE is_active)          AS total_categories,
            (SELECT COUNT(*) FROM subcategories WHERE is_active)       AS total_subcategories,
            (SELECT COUNT(*) FROM products WHERE is_active AND stock_quantity < 10) AS flagged_products,
            (SELECT AVG(selling_price) FROM products WHERE is_active)  AS avg_price
    """))).fetchone()
    admin_cache_set(
        "stats",
        AdminStatsOut(
            total_products=row.total_products,
            total_categories=row.total_categories,
            total_subcategories=row.total_subcategories,
            flagged_products=row.flagged_products,
            avg_price=round(float(row.avg_price or 0), 2),
        ),
    )

    admin_cache_set("dashboard", await _fetch_admin_dashboard(db))

    first_products_key = _admin_products_cache_key(
        page=1,
        per_page=25,
        category_id=None,
        subcategory_id=None,
        search=None,
        stock=None,
        kitchen_culture=None,
        sort="none",
        active_filter="active",
    )
    admin_cache_set(
        first_products_key,
        await _fetch_admin_products_page(
            db,
            page=1,
            per_page=25,
            category_id=None,
            subcategory_id=None,
            search=None,
            stock=None,
            kitchen_culture=None,
            sort="none",
            active_filter="active",
        ),
    )
    cat_rows = (await db.execute(_text("""
        SELECT
            c.category_id, c.category_name, c.description, c.slug,
            c.icon_image_url, c.banner_image_url, c.is_active, c.display_order,
            COUNT(p.product_id) AS item_count
        FROM categories c
        LEFT JOIN products p ON p.category_id = c.category_id
        GROUP BY c.category_id, c.category_name, c.description, c.slug,
                 c.icon_image_url, c.banner_image_url, c.is_active, c.display_order
        ORDER BY c.display_order, c.category_name
    """))).fetchall()
    admin_cache_set(
        "categories",
        [
            {
                "category_id": row.category_id,
                "category_name": row.category_name,
                "description": row.description,
                "slug": row.slug,
                "icon_image_url": row.icon_image_url,
                "banner_image_url": row.banner_image_url,
                "item_count": row.item_count,
                "is_active": row.is_active,
                "display_order": row.display_order,
            }
            for row in cat_rows
        ],
    )

    admin_cache_set("spotlight", await _fetch_admin_spotlight(db))

    banner_rows = await ensure_banner_chains(db)
    admin_cache_set("banners", serialize_banners(banner_rows))

    culture_rows = await ensure_culture_chains(db)
    admin_cache_set("cultures", serialize_cultures(culture_rows))

    admin_cache_set("settings", await load_public_site_settings(db))


def _slug(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_]+", "-", s) or "item"


def _image_to_dict(img: ProductImage) -> dict:
    return {
        "id": img.id,
        "productId": img.product_id,
        "imageUrl": img.image_url,
        "isPrimary": bool(img.is_primary),
        "displayOrder": int(img.display_order or 0),
        "altText": img.alt_text or "",
    }


async def _get_product_or_404(db: AsyncSession, product_id: str) -> Product:
    result = await db.execute(
        select(Product)
        .options(
            joinedload(Product.images),
            joinedload(Product.category),
            joinedload(Product.subcategory),
        )
        .where(Product.product_id == product_id)
    )
    prod = result.unique().scalar_one_or_none()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    return prod


async def _purge_product_images(db: AsyncSession, product_id: str) -> None:
    result = await db.execute(select(ProductImage).where(ProductImage.product_id == product_id))
    for img in result.scalars():
        if img.image_url.startswith("/uploads/products/"):
            local_path = PRODUCT_UPLOADS_DIR / Path(img.image_url).name
            if local_path.exists():
                local_path.unlink(missing_ok=True)
        elif "res.cloudinary.com" in img.image_url:
            try:
                delete_by_url(img.image_url)
            except Exception:
                pass
        await db.delete(img)


async def _permanently_delete_product(db: AsyncSession, prod: Product) -> None:
    await _purge_product_images(db, prod.product_id)
    await db.delete(prod)
    await db.flush()


async def _next_display_order(db: AsyncSession, product_id: str) -> int:
    result = await db.execute(
        select(func.coalesce(func.max(ProductImage.display_order), -1)).where(
            ProductImage.product_id == product_id
        )
    )
    return int(result.scalar_one()) + 1


async def _clear_primary_flags(db: AsyncSession, product_id: str) -> None:
    result = await db.execute(select(ProductImage).where(ProductImage.product_id == product_id))
    for img in result.scalars():
        img.is_primary = False


async def _add_product_image_record(
    db: AsyncSession,
    product_id: str,
    image_url: str,
    *,
    is_primary: bool = False,
    alt_text: str | None = None,
) -> ProductImage:
    existing = (
        await db.execute(select(ProductImage).where(ProductImage.product_id == product_id))
    ).scalars().all()
    make_primary = is_primary or not existing
    if make_primary:
        await _clear_primary_flags(db, product_id)
    img = ProductImage(
        product_id=product_id,
        image_url=image_url,
        alt_text=alt_text,
        is_primary=make_primary,
        display_order=await _next_display_order(db, product_id),
    )
    db.add(img)
    await db.flush()
    return img


@router.get("/stats", response_model=AdminStatsOut)
async def admin_stats(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    cached = admin_cache_get("stats")
    if cached is not None:
        return cached

    from sqlalchemy import text as _text
    row = (await db.execute(_text("""
        SELECT
            (SELECT COUNT(*) FROM products WHERE is_active)              AS total_products,
            (SELECT COUNT(*) FROM categories WHERE is_active)          AS total_categories,
            (SELECT COUNT(*) FROM subcategories WHERE is_active)       AS total_subcategories,
            (SELECT COUNT(*) FROM products WHERE is_active AND stock_quantity < 10) AS flagged_products,
            (SELECT AVG(selling_price) FROM products WHERE is_active)  AS avg_price
    """))).fetchone()
    result = AdminStatsOut(
        total_products=row.total_products,
        total_categories=row.total_categories,
        total_subcategories=row.total_subcategories,
        flagged_products=row.flagged_products,
        avg_price=round(float(row.avg_price or 0), 2),
    )
    admin_cache_set("stats", result)
    return result


@router.get("/categories")
async def admin_categories(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    cached = admin_cache_get("categories")
    if cached is not None:
        return cached

    from sqlalchemy import text as _text
    result = await db.execute(_text("""
        SELECT
            c.category_id, c.category_name, c.description, c.slug,
            c.icon_image_url, c.banner_image_url, c.is_active, c.display_order,
            COUNT(p.product_id) AS item_count
        FROM categories c
        LEFT JOIN products p ON p.category_id = c.category_id
        GROUP BY c.category_id, c.category_name, c.description, c.slug,
                 c.icon_image_url, c.banner_image_url, c.is_active, c.display_order
        ORDER BY c.display_order, c.category_name
    """))
    rows = [
        {
            "category_id": row.category_id,
            "category_name": row.category_name,
            "description": row.description,
            "slug": row.slug,
            "icon_image_url": row.icon_image_url,
            "banner_image_url": row.banner_image_url,
            "item_count": row.item_count,
            "is_active": row.is_active,
            "display_order": row.display_order,
        }
        for row in result.fetchall()
    ]
    admin_cache_set("categories", rows)
    return rows


@router.post("/categories")
async def create_category(
    body: AdminCategoryIn,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    body = _payload(body)
    cat_id = body.get("category_id") or body.get("ProductCategoryID")
    name = body.get("category_name") or body.get("CategoryName")
    if not cat_id or not name:
        raise HTTPException(status_code=422, detail="category_id and category_name required")
    cat = Category(
        category_id=cat_id,
        category_name=name,
        description=body.get("description"),
        slug=_slug(name),
    )
    db.add(cat)
    await db.flush()
    invalidate_catalog_cache()
    return {"ok": True, "category_id": cat_id}


@router.put("/categories/{category_id}")
async def update_category(
    category_id: str,
    body: AdminCategoryIn,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    body = _payload(body)
    result = await db.execute(select(Category).where(Category.category_id == category_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    if "category_name" in body or "CategoryName" in body:
        cat.category_name = body.get("category_name") or body.get("CategoryName")
    for k in ("description", "slug", "icon_image_url", "banner_image_url", "display_order", "is_active"):
        if k in body:
            setattr(cat, k, body[k])
    invalidate_catalog_cache()
    return {"ok": True}


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: str,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Category).where(Category.category_id == category_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    cat.is_active = False
    invalidate_catalog_cache()
    return {"ok": True}


@router.get("/subcategories")
async def admin_subcategories(
    category_id: str | None = None,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"subcategories:{category_id or 'all'}"
    cached = admin_cache_get(cache_key)
    if cached is not None:
        return cached

    from sqlalchemy import text as _text
    where = "AND s.category_id = :cat_id" if category_id else ""
    result = await db.execute(_text(f"""
        SELECT
            s.subcategory_id, s.category_id, s.subcategory_name, s.description,
            s.slug, s.is_active, s.display_order,
            COUNT(p.product_id) AS product_count
        FROM subcategories s
        LEFT JOIN products p ON p.subcategory_id = s.subcategory_id
        WHERE true {where}
        GROUP BY s.subcategory_id, s.category_id, s.subcategory_name,
                 s.description, s.slug, s.is_active, s.display_order
        ORDER BY s.display_order, s.subcategory_name
    """), {"cat_id": category_id} if category_id else {})
    rows = [
        {
            "subcategory_id": row.subcategory_id,
            "category_id": row.category_id,
            "subcategory_name": row.subcategory_name,
            "description": row.description,
            "slug": row.slug,
            "is_active": row.is_active,
            "display_order": row.display_order,
            "product_count": row.product_count,
        }
        for row in result.fetchall()
    ]
    admin_cache_set(cache_key, rows)
    return rows


@router.post("/subcategories")
async def create_subcategory(
    body: AdminSubcategoryIn,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    body = _payload(body)
    sub_id = body.get("subcategory_id") or body.get("ProductSubCategoryID")
    cat_id = body.get("category_id") or body.get("ProductCategoryID")
    name = body.get("subcategory_name") or body.get("SubCategoryName")
    if not all([sub_id, cat_id, name]):
        raise HTTPException(status_code=422, detail="subcategory_id, category_id, subcategory_name required")
    db.add(
        Subcategory(
            subcategory_id=sub_id,
            category_id=cat_id,
            subcategory_name=name,
            description=body.get("description"),
            slug=_slug(f"{cat_id}-{name}"),
        )
    )
    invalidate_catalog_cache()
    return {"ok": True}


@router.get("/products")
async def admin_products(
    response: Response,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=500),
    category_id: str | None = None,
    subcategory_id: str | None = None,
    search: str | None = None,
    stock: str | None = None,
    kitchen_culture: str | None = None,
    sort: str | None = Query(None, pattern="^(none|name_asc|name_desc|category_asc|category_desc|discount_asc|discount_desc|stock_asc|stock_desc)$"),
    active_filter: str = Query("active", pattern="^(active|inactive|all)$"),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    sort_key = sort or "none"
    cache_key = _admin_products_cache_key(
        page=page,
        per_page=per_page,
        category_id=category_id,
        subcategory_id=subcategory_id,
        search=search,
        stock=stock,
        kitchen_culture=kitchen_culture,
        sort=sort_key,
        active_filter=active_filter,
    )
    cached = admin_cache_get(cache_key)
    if cached is not None:
        return cached

    result = await _fetch_admin_products_page(
        db,
        page=page,
        per_page=per_page,
        category_id=category_id,
        subcategory_id=subcategory_id,
        search=search,
        stock=stock,
        kitchen_culture=kitchen_culture,
        sort=sort_key,
        active_filter=active_filter,
    )
    admin_cache_set(cache_key, result)
    return result


@router.get("/products/discounted")
async def discounted_products(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    cached = admin_cache_get("discountedProducts")
    if cached is not None:
        return cached

    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.subcategory))
        .where(Product.is_active.is_(True), Product.discount_percent > 0)
        .order_by(Product.discount_percent.desc())
        .limit(500)
    )
    rows = [
        {
            "productId": p.product_id,
            "productName": p.product_name,
            "categoryName": p.category.category_name if p.category else "",
            "subCategoryName": p.subcategory.subcategory_name if p.subcategory else "",
            "comparePrice": float(p.compare_price) if p.compare_price else None,
            "sellingPrice": float(p.selling_price),
            "discountPercent": int(p.discount_percent or 0),
        }
        for p in result.scalars()
    ]
    admin_cache_set("discountedProducts", rows)
    return rows


@router.post("/products/bulk-discount")
async def bulk_discount(body: AdminBulkDiscountIn, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    body = _payload(body)
    pct = int(body.get("discount_percent", 0))
    if pct < 0 or pct > 100:
        raise HTTPException(status_code=422, detail="Invalid discount")
    q = select(Product).where(Product.is_active.is_(True))
    if body.get("subcategory_id"):
        q = q.where(Product.subcategory_id == body["subcategory_id"])
    elif body.get("category_id"):
        q = q.where(Product.category_id == body["category_id"])
    result = await db.execute(q)
    count = 0
    for p in result.scalars():
        base = float(p.compare_price) if p.compare_price else float(p.selling_price or 0)
        if base <= 0:
            continue
        p.compare_price = Decimal(str(base))
        p.discount_percent = pct
        p.selling_price = Decimal(str(round(base * (1 - pct / 100), 2)))
        p.is_hot_offer = pct > 0
        count += 1
    invalidate_catalog_cache()
    return {"ok": True, "affected": count}


@router.post("/products/clear-discounts")
async def clear_discounts(body: AdminClearDiscountsIn | None = None, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    body = _payload(body) if body is not None else None
    ids = (body or {}).get("product_ids") or []
    q = select(Product).where(Product.discount_percent > 0)
    if ids:
        q = q.where(Product.product_id.in_(ids))
    result = await db.execute(q)
    count = 0
    for p in result.scalars():
        if p.compare_price is not None:
            p.selling_price = p.compare_price
        p.discount_percent = 0
        p.compare_price = None
        p.is_hot_offer = False
        count += 1
    invalidate_catalog_cache()
    return {"ok": True, "affected": count}


@router.post("/products/bulk-clear-discounts")
async def bulk_clear_discounts(body: AdminClearDiscountsIn, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await clear_discounts(body, user=user, db=db)


@router.post("/products/bulk")
async def bulk_product_action(body: AdminBulkProductActionIn, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    body = _payload(body)
    ids = body.get("product_ids") or []
    action = body.get("action")
    if not ids:
        raise HTTPException(status_code=422, detail="No products selected")
    result = await db.execute(select(Product).where(Product.product_id.in_(ids)))
    products = list(result.scalars())
    for p in products:
        if action == "activate":
            p.is_active = True
        elif action == "deactivate":
            p.is_active = False
        elif action == "delete":
            await _permanently_delete_product(db, p)
        elif action == "category" and body.get("category_id"):
            p.category_id = body["category_id"]
            if body.get("subcategory_id"):
                p.subcategory_id = body["subcategory_id"]
    invalidate_catalog_cache()
    return {"ok": True, "affected": len(products)}


@router.get("/products/{product_id}")
async def get_admin_product(
    product_id: str,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"product:{product_id}"
    cached = admin_cache_get(cache_key)
    if cached is not None:
        return cached

    prod = await _get_product_or_404(db, product_id)
    img = primary_image(prod) if prod.images else None
    result = admin_product_to_dict(prod, img)
    admin_cache_set(cache_key, result)
    return result


@router.post("/products")
async def create_product(
    body: AdminProductIn,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    body = _payload(body)
    pid = body.get("product_id") or body.get("productId")
    if not pid:
        raise HTTPException(status_code=422, detail="product_id required")
    prod = Product(
        product_id=pid,
        category_id=body["category_id"],
        subcategory_id=body["subcategory_id"],
        product_name=body["product_name"],
        brand=body.get("brand"),
        slug=_slug(f"{pid}-{body['product_name']}"),
        description=body.get("description"),
        selling_price=Decimal(str(body.get("selling_price", 0))),
        compare_price=Decimal(str(body["compare_price"])) if body.get("compare_price") else None,
        discount_percent=body.get("discount_percent"),
        unit_label=body.get("unit_label", ""),
        weight_kg=body.get("weight_kg"),
        stock_quantity=body.get("stock_quantity", 0),
        min_order_qty=body.get("min_order_qty", 1),
        is_wholesale=bool(body.get("is_wholesale", False)),
        is_featured=bool(body.get("is_featured", False)),
        is_best_seller=bool(body.get("is_best_seller", False)),
        is_new_arrival=bool(body.get("is_new_arrival", False)),
        is_hot_offer=bool(body.get("is_hot_offer", False)),
        is_exclusive=bool(body.get("is_exclusive", False)),
        is_active=bool(body.get("is_active", True)),
        kitchen_culture=normalize_kitchen_culture(body.get("kitchen_culture")),
    )
    db.add(prod)
    invalidate_catalog_cache()
    return {"ok": True, "product_id": pid}


@router.put("/products/{product_id}")
async def update_product(
    product_id: str,
    body: AdminProductIn,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    body = _payload(body)
    result = await db.execute(select(Product).where(Product.product_id == product_id))
    prod = result.scalar_one_or_none()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    field_map = {
        "product_name": "product_name",
        "brand": "brand",
        "description": "description",
        "category_id": "category_id",
        "subcategory_id": "subcategory_id",
        "unit_label": "unit_label",
        "weight_kg": "weight_kg",
        "is_active": "is_active",
        "is_featured": "is_featured",
        "is_best_seller": "is_best_seller",
        "is_new_arrival": "is_new_arrival",
        "is_hot_offer": "is_hot_offer",
        "is_exclusive": "is_exclusive",
        "is_wholesale": "is_wholesale",
        "stock_quantity": "stock_quantity",
        "min_order_qty": "min_order_qty",
        "discount_percent": "discount_percent",
        "kitchen_culture": "kitchen_culture",
    }
    decimal_fields = {"selling_price", "compare_price"}
    for key, attr in field_map.items():
        if key in body:
            value = body[key]
            if key == "kitchen_culture":
                value = normalize_kitchen_culture(value)
            setattr(prod, attr, value)
    for key in decimal_fields:
        if key in body and body[key] is not None:
            setattr(prod, key, Decimal(str(body[key])))
    if "discount_percent" in body:
        pct = int(body.get("discount_percent") or 0)
        if pct > 0 and "is_hot_offer" not in body:
            prod.is_hot_offer = True
        elif pct == 0:
            prod.compare_price = None
            if "is_hot_offer" not in body:
                prod.is_hot_offer = False
    invalidate_catalog_cache()
    return {"ok": True}


@router.delete("/products/{product_id}")
async def delete_product(
    product_id: str,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Product).where(Product.product_id == product_id))
    prod = result.scalar_one_or_none()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    await _permanently_delete_product(db, prod)
    invalidate_catalog_cache()
    return {"ok": True}


@router.get("/products/{product_id}/images")
async def list_product_images(
    product_id: str,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _get_product_or_404(db, product_id)
    result = await db.execute(
        select(ProductImage)
        .where(ProductImage.product_id == product_id)
        .order_by(ProductImage.is_primary.desc(), ProductImage.display_order, ProductImage.id)
    )
    return [_image_to_dict(img) for img in result.scalars()]


@router.post("/products/{product_id}/images")
async def add_product_image_url(
    product_id: str,
    body: AdminProductImageIn,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    body = _payload(body)
    await _get_product_or_404(db, product_id)
    image_url = (body.get("image_url") or body.get("imageUrl") or "").strip()
    if not image_url:
        raise HTTPException(status_code=422, detail="image_url required")
    img = await _add_product_image_record(
        db,
        product_id,
        image_url,
        is_primary=bool(body.get("is_primary") or body.get("isPrimary")),
        alt_text=body.get("alt_text") or body.get("altText"),
    )
    invalidate_catalog_cache()
    return _image_to_dict(img)


@router.post("/products/{product_id}/images/upload")
async def upload_product_images(
    product_id: str,
    files: list[UploadFile] = File(...),
    is_primary: bool = Form(False),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _get_product_or_404(db, product_id)
    if not files:
        raise HTTPException(status_code=422, detail="No files uploaded")

    PRODUCT_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    created: list[dict] = []
    first = True
    settings = get_settings()
    for upload in files:
        if not upload.filename:
            continue
        ext = Path(upload.filename).suffix.lower()
        if ext not in ALLOWED_IMAGE_EXT:
            raise HTTPException(status_code=422, detail=f"Unsupported file type: {ext}")
        data = await upload.read()
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=422, detail="File too large (max 5 MB)")
        if not settings.cloudinary_configured:
            raise HTTPException(
                status_code=503,
                detail="Cloudinary is required for image uploads. Set CLOUDINARY_* in .env",
            )
        try:
            result = upload_upload_file(data, upload.filename, subfolder="products")
            url = result["secure_url"]
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Cloudinary upload failed: {exc}") from exc
        img = await _add_product_image_record(
            db,
            product_id,
            url,
            is_primary=is_primary and first,
        )
        created.append(_image_to_dict(img))
        first = False

    if not created:
        raise HTTPException(status_code=422, detail="No valid image files")
    invalidate_catalog_cache()
    return {"items": created}


@router.patch("/products/{product_id}/images/{image_id}")
async def update_product_image(
    product_id: str,
    image_id: int,
    body: AdminProductImageIn,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    body = _payload(body)
    await _get_product_or_404(db, product_id)
    result = await db.execute(
        select(ProductImage).where(
            ProductImage.id == image_id,
            ProductImage.product_id == product_id,
        )
    )
    img = result.scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    if body.get("is_primary") or body.get("isPrimary"):
        await _clear_primary_flags(db, product_id)
        img.is_primary = True
    if "alt_text" in body or "altText" in body:
        img.alt_text = body.get("alt_text") or body.get("altText")
    if "display_order" in body or "displayOrder" in body:
        img.display_order = int(body.get("display_order") or body.get("displayOrder") or 0)
    invalidate_catalog_cache()
    return _image_to_dict(img)


@router.delete("/products/{product_id}/images/{image_id}")
async def delete_product_image(
    product_id: str,
    image_id: int,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _get_product_or_404(db, product_id)
    result = await db.execute(
        select(ProductImage).where(
            ProductImage.id == image_id,
            ProductImage.product_id == product_id,
        )
    )
    img = result.scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    was_primary = img.is_primary
    if img.image_url.startswith("/uploads/products/"):
        local_path = PRODUCT_UPLOADS_DIR / Path(img.image_url).name
        if local_path.exists():
            local_path.unlink(missing_ok=True)
    elif "res.cloudinary.com" in img.image_url:
        try:
            delete_by_url(img.image_url)
        except Exception:
            pass
    await db.delete(img)
    await db.flush()
    if was_primary:
        remaining = (
            await db.execute(
                select(ProductImage)
                .where(ProductImage.product_id == product_id)
                .order_by(ProductImage.display_order, ProductImage.id)
            )
        ).scalars().first()
        if remaining:
            remaining.is_primary = True
    invalidate_catalog_cache()
    return {"ok": True}


@router.get("/banners")
async def admin_banners(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    cached = admin_cache_get("banners")
    if cached is not None:
        return cached

    banners = await ensure_banner_chains(db)
    rows = serialize_banners(banners)
    admin_cache_set("banners", rows)
    return rows


@router.post("/banners/upload")
async def upload_banner_image(
    file: UploadFile = File(...),
    user: User = Depends(require_admin),
):
    if not file.filename:
        raise HTTPException(status_code=422, detail="No file uploaded")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXT:
        raise HTTPException(status_code=422, detail=f"Unsupported file type: {ext}")
    data = await file.read()
    if len(data) > MAX_BANNER_BYTES:
        raise HTTPException(status_code=422, detail="File too large (max 12 MB)")

    settings = get_settings()
    if not settings.cloudinary_configured:
        raise HTTPException(
            status_code=503,
            detail="Cloudinary is required for banner uploads. Set CLOUDINARY_* in .env",
        )
    try:
        result = upload_upload_file(data, file.filename, subfolder="promotion-banners")
        url = result["secure_url"]
        return {"imageUrl": url, "url": url}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Cloudinary upload failed: {exc}") from exc


@router.post("/banners/{banner_id}/move")
async def move_banner_order(
    banner_id: int,
    body: dict,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    direction = (body.get("direction") or "").strip().lower()
    if direction not in ("left", "right"):
        raise HTTPException(status_code=422, detail="direction must be 'left' or 'right'")

    banners = await ensure_banner_chains(db)
    banner = next((b for b in banners if b.id == banner_id), None)
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    if not move_banner_in_chain(banner, banners, direction):
        raise HTTPException(status_code=400, detail="Banner cannot move further in that direction")

    await db.commit()
    invalidate_admin_site_cache("banners")
    invalidate_catalog_cache()
    return {"ok": True}


@router.post("/banners")
async def create_banner(body: dict, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    is_active = body.get("is_active", True)
    banner = SiteBanner(
        title=body.get("title", "Banner"),
        subtitle=body.get("subtitle"),
        image_url=body["image_url"],
        link_url=body.get("link_url"),
        display_order=0,
        is_active=is_active,
    )
    db.add(banner)
    await db.flush()

    banners = await load_all_banners(db)
    if "display_order" in body and body["display_order"] is not None:
        insert_at_index(banner, banners, int(body["display_order"]))
    else:
        append_to_tail(banner, banners)

    await db.commit()
    invalidate_admin_site_cache("banners")
    invalidate_catalog_cache()
    return {"ok": True, "id": banner.id}


@router.put("/banners/{banner_id}")
async def update_banner(
    banner_id: int,
    body: dict,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    banners = await ensure_banner_chains(db)
    banner = next((b for b in banners if b.id == banner_id), None)
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")

    new_active = body["is_active"] if "is_active" in body else bool(banner.is_active)
    if "is_active" in body and bool(banner.is_active) != bool(new_active):
        relocate_on_active_change(banner, banners, bool(new_active))

    direction = (body.get("direction") or "").strip().lower()
    if direction in ("left", "right"):
        if not move_banner_in_chain(banner, banners, direction):
            raise HTTPException(status_code=400, detail="Banner cannot move further in that direction")
        await db.commit()
        invalidate_admin_site_cache("banners")
        invalidate_catalog_cache()
        return {"ok": True}

    for k in ("title", "subtitle", "image_url", "link_url"):
        if k in body:
            setattr(banner, k, body[k])

    if "display_order" in body and body["display_order"] is not None:
        insert_at_index(banner, banners, int(body["display_order"]))

    await db.commit()
    invalidate_admin_site_cache("banners")
    invalidate_catalog_cache()
    return {"ok": True}


@router.delete("/banners/{banner_id}")
async def delete_banner(
    banner_id: int,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    banners = await ensure_banner_chains(db)
    banner = next((b for b in banners if b.id == banner_id), None)
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    unlink_banner(banner, banners)
    await db.delete(banner)
    await db.commit()
    invalidate_admin_site_cache("banners")
    invalidate_catalog_cache()
    return {"ok": True}


@router.get("/cultures")
async def admin_cultures(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    cached = admin_cache_get("cultures")
    if cached is not None:
        return cached

    items = await ensure_culture_chains(db)
    rows = serialize_cultures(items)
    admin_cache_set("cultures", rows)
    return rows


@router.post("/cultures/upload")
async def upload_culture_image(
    file: UploadFile = File(...),
    user: User = Depends(require_admin),
):
    if not file.filename:
        raise HTTPException(status_code=422, detail="No file uploaded")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXT:
        raise HTTPException(status_code=422, detail=f"Unsupported file type: {ext}")
    data = await file.read()
    if len(data) > MAX_BANNER_BYTES:
        raise HTTPException(status_code=422, detail="File too large (max 12 MB)")

    settings = get_settings()
    if not settings.cloudinary_configured:
        raise HTTPException(
            status_code=503,
            detail="Cloudinary is required for culture uploads. Set CLOUDINARY_* in .env",
        )
    try:
        result = upload_upload_file(data, file.filename, subfolder="culture-banners")
        url = result["secure_url"]
        return {"imageUrl": url, "url": url}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Cloudinary upload failed: {exc}") from exc


@router.post("/cultures")
async def create_culture(body: dict, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    is_active = body.get("is_active", True)
    culture = CultureBanner(
        title=body.get("title", "Culture Banner"),
        image_url=body["image_url"],
        link_url=body.get("link_url") or "products.html",
        display_order=0,
        is_active=is_active,
    )
    db.add(culture)
    await db.flush()

    items = await load_all_cultures(db)
    if "display_order" in body and body["display_order"] is not None:
        insert_culture_at_index(culture, items, int(body["display_order"]))
    else:
        append_culture_to_tail(culture, items)

    await db.commit()
    invalidate_admin_site_cache("cultures")
    invalidate_catalog_cache()
    return {"ok": True, "id": culture.id}


@router.put("/cultures/{culture_id}")
async def update_culture(
    culture_id: int,
    body: dict,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    items = await ensure_culture_chains(db)
    culture = next((b for b in items if b.id == culture_id), None)
    if not culture:
        raise HTTPException(status_code=404, detail="Culture banner not found")

    new_active = body["is_active"] if "is_active" in body else bool(culture.is_active)
    if "is_active" in body and bool(culture.is_active) != bool(new_active):
        relocate_culture_on_active_change(culture, items, bool(new_active))

    direction = (body.get("direction") or "").strip().lower()
    if direction in ("left", "right"):
        if not move_culture(culture, items, direction):
            raise HTTPException(status_code=400, detail="Culture banner cannot move further in that direction")
        await db.commit()
        invalidate_admin_site_cache("cultures")
        invalidate_catalog_cache()
        return {"ok": True}

    for k in ("title", "image_url", "link_url"):
        if k in body:
            setattr(culture, k, body[k])

    if "display_order" in body and body["display_order"] is not None:
        insert_culture_at_index(culture, items, int(body["display_order"]))

    await db.commit()
    invalidate_admin_site_cache("cultures")
    invalidate_catalog_cache()
    return {"ok": True}


@router.delete("/cultures/{culture_id}")
async def delete_culture(
    culture_id: int,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    items = await ensure_culture_chains(db)
    culture = next((b for b in items if b.id == culture_id), None)
    if not culture:
        raise HTTPException(status_code=404, detail="Culture banner not found")
    unlink_culture(culture, items)
    await db.delete(culture)
    await db.commit()
    invalidate_admin_site_cache("cultures")
    invalidate_catalog_cache()
    return {"ok": True}


@router.get("/kitchen-cultures")
async def admin_kitchen_cultures(user: User = Depends(require_admin)):
    return KITCHEN_CULTURES


@router.get("/coupons", response_model=list[CouponOut])
async def list_coupons(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SiteSetting).where(SiteSetting.setting_key == "coupons"))
    setting = result.scalar_one_or_none()
    if not setting:
        return []
    try:
        data = json.loads(setting.setting_value)
    except json.JSONDecodeError:
        return []
    return [CouponOut(**c) for c in data]


@router.put("/coupons")
async def save_coupons(
    coupons: list[dict],
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SiteSetting).where(SiteSetting.setting_key == "coupons"))
    setting = result.scalar_one_or_none()
    payload = json.dumps(coupons)
    if setting:
        setting.setting_value = payload
    else:
        db.add(SiteSetting(setting_key="coupons", setting_value=payload, setting_type="json"))
    invalidate_catalog_cache()
    return {"ok": True}


@router.get("/spotlight")
async def admin_spotlight(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    cached = admin_cache_get("spotlight")
    if cached is not None:
        return cached
    result = await _fetch_admin_spotlight(db)
    admin_cache_set("spotlight", result)
    return result


async def _fetch_admin_dashboard(db: AsyncSession) -> dict:
    from sqlalchemy import text as _text

    row = (await db.execute(_text("""
        SELECT
            COUNT(*) FILTER (WHERE is_featured    AND is_active) AS featured,
            COUNT(*) FILTER (WHERE is_best_seller AND is_active) AS best_sellers,
            COUNT(*) FILTER (WHERE is_new_arrival AND is_active) AS new_arrivals,
            COUNT(*) FILTER (WHERE is_hot_offer   AND is_active) AS hot_offers,
            COUNT(*) FILTER (WHERE is_exclusive   AND is_active) AS exclusive
        FROM products
    """))).fetchone()
    stats_row = (await db.execute(_text("""
        SELECT
            (SELECT COUNT(*) FROM products WHERE is_active)              AS total_products,
            (SELECT COUNT(*) FROM categories WHERE is_active)          AS total_categories,
            (SELECT COUNT(*) FROM subcategories WHERE is_active)       AS total_subcategories,
            (SELECT COUNT(*) FROM products WHERE is_active AND stock_quantity < 20) AS low_stock,
            (SELECT COUNT(*) FROM products WHERE is_active AND discount_percent > 0) AS on_sale,
            (SELECT AVG(selling_price) FROM products WHERE is_active)  AS avg_price
    """))).fetchone()
    return {
        "spotlightCounts": {
            "featured": row.featured,
            "bestSellers": row.best_sellers,
            "newArrivals": row.new_arrivals,
            "hotOffers": row.hot_offers,
            "exclusive": row.exclusive,
        },
        "catalogStats": {
            "totalProducts": stats_row.total_products,
            "totalCategories": stats_row.total_categories,
            "totalSubcategories": stats_row.total_subcategories,
            "lowStock": stats_row.low_stock,
            "onSale": stats_row.on_sale,
            "avgPrice": round(float(stats_row.avg_price or 0), 2),
        },
    }


@router.get("/dashboard")
async def admin_dashboard(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    cached = admin_cache_get("dashboard")
    if cached is not None:
        return cached

    result = await _fetch_admin_dashboard(db)
    admin_cache_set("dashboard", result)
    return result


@router.get("/brands")
async def admin_brands(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    cached = admin_cache_get("brands")
    if cached is not None:
        return cached

    from sqlalchemy import text as _text
    result = await db.execute(
        _text("""
            SELECT DISTINCT brand FROM products
            WHERE brand IS NOT NULL AND TRIM(brand) <> ''
            ORDER BY brand
        """)
    )
    rows = [row.brand for row in result.fetchall()]
    admin_cache_set("brands", rows)
    return rows


@router.get("/testimonials")
async def admin_testimonials(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    cached = admin_cache_get("testimonials")
    if cached is not None:
        return cached

    result = await db.execute(select(Testimonial).order_by(Testimonial.display_order, Testimonial.id))
    rows = [
        {
            "id": t.id,
            "customerName": t.customer_name,
            "customerInitial": t.customer_initial,
            "isVerifiedCustomer": t.is_verified_customer,
            "rating": t.rating,
            "quote": t.quote,
            "isFeatured": t.is_featured,
            "displayOrder": t.display_order,
            "createdAt": t.created_at.isoformat() if t.created_at else None,
        }
        for t in result.scalars()
    ]
    admin_cache_set("testimonials", rows)
    return rows


@router.post("/testimonials")
async def create_testimonial(body: dict, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    t = Testimonial(
        customer_name=body["customer_name"],
        customer_initial=body.get("customer_initial"),
        is_verified_customer=bool(body.get("is_verified_customer", True)),
        rating=int(body.get("rating", 5)),
        quote=body["quote"],
        is_featured=bool(body.get("is_featured", True)),
        display_order=int(body.get("display_order", 0)),
    )
    db.add(t)
    await db.flush()
    invalidate_admin_site_cache("testimonials", "spotlight")
    return {"ok": True, "id": t.id}


@router.put("/testimonials/{testimonial_id}")
async def update_testimonial(
    testimonial_id: int,
    body: dict,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Testimonial).where(Testimonial.id == testimonial_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Testimonial not found")
    for k in (
        "customer_name",
        "customer_initial",
        "is_verified_customer",
        "rating",
        "quote",
        "is_featured",
        "display_order",
    ):
        if k in body:
            setattr(t, k, body[k])
    invalidate_admin_site_cache("testimonials", "spotlight")
    return {"ok": True}


@router.delete("/testimonials/{testimonial_id}")
async def delete_testimonial(
    testimonial_id: int,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Testimonial).where(Testimonial.id == testimonial_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Testimonial not found")
    await db.delete(t)
    invalidate_admin_site_cache("testimonials", "spotlight")
    return {"ok": True}


@router.get("/settings")
async def get_site_settings(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    cached = admin_cache_get("settings")
    if cached is not None:
        return cached
    payload = await load_public_site_settings(db)
    admin_cache_set("settings", payload)
    return payload


@router.put("/settings")
async def save_site_settings(
    body: dict,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    for key, value in body.items():
        if key not in SITE_SETTING_KEYS:
            continue
        result = await db.execute(select(SiteSetting).where(SiteSetting.setting_key == key))
        setting = result.scalar_one_or_none()
        val_str = value if isinstance(value, str) else json.dumps(value)
        if setting:
            setting.setting_value = val_str
        else:
            db.add(SiteSetting(setting_key=key, setting_value=val_str, setting_type="text"))
    invalidate_catalog_cache()
    invalidate_admin_site_cache("settings")
    return {"ok": True}


@router.put("/subcategories/{subcategory_id}")
async def update_subcategory(
    subcategory_id: str,
    body: dict,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Subcategory).where(Subcategory.subcategory_id == subcategory_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subcategory not found")
    for k in ("subcategory_name", "description", "slug", "display_order", "is_active", "category_id"):
        if k in body:
            setattr(sub, k, body[k])
    invalidate_catalog_cache()
    return {"ok": True}


@router.delete("/subcategories/{subcategory_id}")
async def delete_subcategory(
    subcategory_id: str,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Subcategory).where(Subcategory.subcategory_id == subcategory_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subcategory not found")
    sub.is_active = False
    invalidate_catalog_cache()
    return {"ok": True}


# ── Contact Submissions ───────────────────────────────────────────────────────

@router.get("/contact-submissions")
async def admin_contact_submissions(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ContactSubmission).order_by(ContactSubmission.submitted_at.desc())
    )
    rows = result.scalars().all()
    unread = sum(1 for r in rows if not r.is_read)
    return {
        "total": len(rows),
        "unread": unread,
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "email": r.email,
                "phone": r.phone or "",
                "enquiryType": r.enquiry_type or "",
                "message": r.message,
                "isRead": r.is_read,
                "submittedAt": r.submitted_at.isoformat() if r.submitted_at else "",
            }
            for r in rows
        ],
    }


@router.put("/contact-submissions/{submission_id}/read")
async def mark_contact_read(
    submission_id: int,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ContactSubmission).where(ContactSubmission.id == submission_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    sub.is_read = True
    await db.commit()
    return {"ok": True}


@router.delete("/contact-submissions/{submission_id}")
async def delete_contact_submission(
    submission_id: int,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ContactSubmission).where(ContactSubmission.id == submission_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    await db.delete(sub)
    await db.commit()
    return {"ok": True}
