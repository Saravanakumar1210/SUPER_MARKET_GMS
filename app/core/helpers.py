"""Backward-compatible re-exports for router imports."""

from app.core.auth import (
    create_session,
    get_current_user,
    hash_password,
    require_admin,
    require_customer,
    require_user,
    security,
    verify_password,
)
from app.core.catalog import (
    build_products_query,
    get_category_stats,
    get_subcategory_stats,
    primary_image,
    product_to_dict,
)
from app.core.pagination import paginate_meta

__all__ = [
    "build_products_query",
    "create_session",
    "get_category_stats",
    "get_current_user",
    "get_subcategory_stats",
    "hash_password",
    "paginate_meta",
    "primary_image",
    "product_to_dict",
    "require_admin",
    "require_customer",
    "require_user",
    "security",
    "verify_password",
]
