-- GMS World Foods PostgreSQL schema (lean — matches live storefront + admin)

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Catalog ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS categories (
    category_id     VARCHAR(10) PRIMARY KEY,
    category_name   VARCHAR(100) NOT NULL,
    description     TEXT,
    slug            VARCHAR(120) UNIQUE NOT NULL,
    icon_image_url  TEXT,
    banner_image_url TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    display_order   SMALLINT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS subcategories (
    subcategory_id      VARCHAR(15) PRIMARY KEY,
    category_id         VARCHAR(10) NOT NULL REFERENCES categories(category_id),
    subcategory_name    VARCHAR(100) NOT NULL,
    description         TEXT,
    slug                VARCHAR(120) UNIQUE NOT NULL,
    is_active           BOOLEAN DEFAULT TRUE,
    display_order       SMALLINT DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
    product_id          VARCHAR(25) PRIMARY KEY,
    subcategory_id      VARCHAR(15) NOT NULL REFERENCES subcategories(subcategory_id),
    category_id         VARCHAR(10) NOT NULL REFERENCES categories(category_id),
    product_name        VARCHAR(255) NOT NULL,
    brand               VARCHAR(100),
    slug                VARCHAR(300) UNIQUE NOT NULL,
    description         TEXT,
    selling_price       NUMERIC(10,2) NOT NULL CHECK (selling_price >= 0),
    compare_price       NUMERIC(10,2),
    discount_percent    SMALLINT DEFAULT 0,
    unit_label          VARCHAR(50) DEFAULT '',
    weight_kg           NUMERIC(8,3),
    is_best_seller      BOOLEAN DEFAULT FALSE,
    is_new_arrival      BOOLEAN DEFAULT FALSE,
    is_hot_offer        BOOLEAN DEFAULT FALSE,
    is_exclusive        BOOLEAN DEFAULT FALSE,
    is_featured         BOOLEAN DEFAULT FALSE,
    is_wholesale        BOOLEAN DEFAULT FALSE,
    min_order_qty       SMALLINT DEFAULT 1,
    stock_quantity      INTEGER DEFAULT 0,
    is_active           BOOLEAN DEFAULT TRUE,
    kitchen_culture     VARCHAR(30),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_subcategory ON products(subcategory_id);
CREATE INDEX IF NOT EXISTS idx_products_featured ON products(is_featured) WHERE is_featured;

CREATE TABLE IF NOT EXISTS product_images (
    id              SERIAL PRIMARY KEY,
    product_id      VARCHAR(25) NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    image_url       TEXT NOT NULL,
    alt_text        VARCHAR(255),
    is_primary      BOOLEAN DEFAULT FALSE,
    display_order   SMALLINT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_product_images_product ON product_images(product_id);

-- ── Admin auth ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100),
    username        VARCHAR(50) UNIQUE,
    email           VARCHAR(255) UNIQUE NOT NULL,
    phone           VARCHAR(30) UNIQUE,
    phone_country   VARCHAR(5) DEFAULT 'GB',
    address         TEXT,
    email_verified  TIMESTAMPTZ,
    role            VARCHAR(20) DEFAULT 'customer',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS accounts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type                    VARCHAR(20) NOT NULL,
    provider                VARCHAR(50) NOT NULL,
    provider_account_id     VARCHAR(255) NOT NULL,
    access_token            TEXT,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(provider, provider_account_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token   TEXT UNIQUE NOT NULL,
    expires         TIMESTAMPTZ NOT NULL
);

-- ── Site content ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS testimonials (
    id                      SERIAL PRIMARY KEY,
    customer_name           VARCHAR(100) NOT NULL,
    customer_initial        VARCHAR(5),
    is_verified_customer    BOOLEAN DEFAULT TRUE,
    rating                  SMALLINT DEFAULT 5 CHECK (rating BETWEEN 1 AND 5),
    quote                   TEXT NOT NULL,
    is_featured             BOOLEAN DEFAULT TRUE,
    display_order           SMALLINT DEFAULT 0,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS newsletter_subscribers (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) UNIQUE NOT NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    subscribed_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS site_banners (
    id              SERIAL PRIMARY KEY,
    title           VARCHAR(150) NOT NULL,
    subtitle        VARCHAR(255),
    image_url       TEXT NOT NULL,
    link_url        TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    display_order   SMALLINT DEFAULT 0,
    prev_banner_id  INTEGER REFERENCES site_banners(id) ON DELETE SET NULL,
    next_banner_id  INTEGER REFERENCES site_banners(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

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
);

CREATE TABLE IF NOT EXISTS site_settings (
    setting_key     VARCHAR(100) PRIMARY KEY,
    setting_value   TEXT NOT NULL,
    setting_type    VARCHAR(20),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Contact form ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS contact_submissions (
    id           SERIAL PRIMARY KEY,
    name         VARCHAR(150) NOT NULL,
    email        VARCHAR(255) NOT NULL,
    phone        VARCHAR(30),
    enquiry_type VARCHAR(100),
    message      TEXT NOT NULL,
    is_read      BOOLEAN DEFAULT FALSE,
    submitted_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contact_submissions_submitted_at
    ON contact_submissions (submitted_at DESC);

-- ── Per-user shopping basket ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_cart_items (
    id            SERIAL PRIMARY KEY,
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_name  VARCHAR(255) NOT NULL,
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, product_name)
);

CREATE INDEX IF NOT EXISTS idx_user_cart_user
    ON user_cart_items (user_id);
