"""One-time idempotent DB indexes for admin search and catalog performance."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("gms")


async def _run_statements(db: AsyncSession, statements: list[str], label: str, *, strict: bool = False) -> None:
    for stmt in statements:
        try:
            await db.execute(text(stmt))
        except Exception as exc:
            if strict:
                await db.rollback()
                raise
            logger.warning("%s setup skipped: %s", label, exc)
    await db.commit()


async def ensure_user_auth_schema(db: AsyncSession) -> None:
    """Customer auth columns on users — required before signup/login."""
    await _run_statements(
        db,
        [
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS username VARCHAR(50)
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_lower
            ON users (LOWER(username))
            WHERE username IS NOT NULL
            """,
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS phone VARCHAR(30)
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone
            ON users (phone)
            WHERE phone IS NOT NULL
            """,
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS address TEXT
            """,
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS phone_country VARCHAR(5) DEFAULT 'GB'
            """,
        ],
        "User auth schema",
        strict=True,
    )


async def ensure_admin_account(db: AsyncSession) -> None:
    """Ensure store admin can sign in with username 'admin' or email."""
    await _run_statements(
        db,
        [
            """
            UPDATE users
            SET username = 'admin'
            WHERE role = 'admin'
              AND LOWER(email) = 'gmsworldfood@gmail.com'
              AND (username IS NULL OR BTRIM(username) = '')
            """,
        ],
        "Admin account",
    )


async def ensure_required_site_schema(db: AsyncSession) -> None:
    """Required tables used by public/admin site features."""
    await _run_statements(
        db,
        [
            """
            CREATE TABLE IF NOT EXISTS contact_submissions (
                id           SERIAL PRIMARY KEY,
                name         VARCHAR(150) NOT NULL,
                email        VARCHAR(255) NOT NULL,
                phone        VARCHAR(30),
                enquiry_type VARCHAR(100),
                message      TEXT NOT NULL,
                is_read      BOOLEAN DEFAULT FALSE,
                submitted_at TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_contact_submissions_submitted_at
            ON contact_submissions (submitted_at DESC)
            """,
            """
            CREATE TABLE IF NOT EXISTS user_cart_items (
                id            SERIAL PRIMARY KEY,
                user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                product_name  VARCHAR(255) NOT NULL,
                quantity      INTEGER NOT NULL CHECK (quantity > 0),
                updated_at    TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (user_id, product_name)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_user_cart_user
            ON user_cart_items (user_id)
            """,
        ],
        "Required site schema",
        strict=True,
    )


async def ensure_performance_indexes(db: AsyncSession) -> None:
    """Create extensions/indexes used by admin product search (safe to re-run)."""
    await ensure_user_auth_schema(db)
    statements = [
        "CREATE EXTENSION IF NOT EXISTS pg_trgm",
        """
        CREATE INDEX IF NOT EXISTS idx_products_name_trgm
        ON products USING gin (product_name gin_trgm_ops)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_products_brand_trgm
        ON products USING gin (brand gin_trgm_ops)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_products_active_name
        ON products (product_name)
        WHERE is_active = true
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_products_active_category
        ON products (category_id)
        WHERE is_active = true
        """,
        """
        ALTER TABLE site_banners
        ADD COLUMN IF NOT EXISTS prev_banner_id INTEGER
        REFERENCES site_banners(id) ON DELETE SET NULL
        """,
        """
        ALTER TABLE site_banners
        ADD COLUMN IF NOT EXISTS next_banner_id INTEGER
        REFERENCES site_banners(id) ON DELETE SET NULL
        """,
        """
        CREATE TABLE IF NOT EXISTS culture_banners (
            id              SERIAL PRIMARY KEY,
            title           VARCHAR(150) NOT NULL,
            image_url       TEXT NOT NULL,
            link_url        TEXT,
            is_active       BOOLEAN DEFAULT TRUE,
            display_order   SMALLINT DEFAULT 0,
            prev_culture_id INTEGER REFERENCES culture_banners(id) ON DELETE SET NULL,
            next_culture_id INTEGER REFERENCES culture_banners(id) ON DELETE SET NULL,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        ALTER TABLE products
        ADD COLUMN IF NOT EXISTS kitchen_culture VARCHAR(30)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_products_kitchen_culture
        ON products (kitchen_culture)
        WHERE kitchen_culture IS NOT NULL
        """,
    ]
    await _run_statements(db, statements, "Performance index")
