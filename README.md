# GMS World Foods — FastAPI + PostgreSQL

GMS World Foods supermarket e-commerce: FastAPI backend, PostgreSQL database, vanilla JS frontend.

## Project layout

```
SUPER_MARKET_V1/
├── app/                    # FastAPI backend
│   ├── main.py             # Single site (storefront + role-gated /admin)
│   ├── config.py           # Settings from .env
│   ├── database.py         # Async SQLAlchemy
│   ├── paths.py            # Project path constants
│   ├── models/             # ORM (catalog, users, site)
│   ├── schemas/            # Pydantic request/response types
│   ├── routers/            # API route modules
│   └── core/               # Auth, catalog queries, pagination, Cloudinary
├── frontend/               # Static site (all users)
│   ├── index.html          # Homepage
│   ├── products.html       # Product listing & filters
│   ├── basket.html         # Shopping basket
│   ├── bucket.html         # Redirect stub → basket.html (legacy URL)
│   ├── about.html, contact.html
│   ├── login.html, signup.html, account.html
│   ├── admin.html          # Store management (admin role)
│   ├── css/                # main.css, admin.css
│   ├── js/                 # Shared storefront + admin scripts
│   ├── assets/             # Store photo, culture icons (fallback images)
│   └── uploads/            # Local product image uploads (gitignored)
├── data/                   # Source data (not served at runtime)
│   ├── catalog/            # CSV files (categories, products, subcategories)
│   └── source-images/      # Original images for one-off Cloudinary upload scripts
│       ├── brand/          # Company logo source
│       ├── categories/, culture-banners/, hero-banners/
│       ├── newsletter/, promotion-banners/, store/
├── database/
│   └── schema.sql          # PostgreSQL DDL reference
├── scripts/                # Maintenance only (does not affect the live site)
│   ├── smoke_check.py      # HTTP checks against a running server
│   ├── uploads/            # Image upload → Cloudinary
│   ├── cloudinary/         # Cloudinary audit / folder reorg
│   ├── catalog/            # Category layout + culture seeding
│   └── maintenance/        # DB checks, cache invalidate, progress
├── tests/                  # API smoke tests (pytest)
├── run.py                  # Start server
├── requirements.txt
├── requirements-dev.txt    # pytest + httpx for smoke tests
├── pytest.ini
├── .env.example            # Copy to .env and fill in values
└── .env                    # Local secrets (not committed)
```

## Setup & run (Windows CMD)

```cmd
cd /d E:\SUPER_MARKET_V1
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:8000** — one site for all users. Sign in from the header; admins also get **Manage store** (same origin, `/admin`). API docs: **http://127.0.0.1:8000/docs**

### Regression checks (before refactors)

```cmd
pip install -r requirements-dev.txt
pytest
```

Optional database-backed smoke tests (requires `.env` PostgreSQL):

```cmd
set GMS_RUN_INTEGRATION=1
pytest -m integration
```

Against a running server:

```cmd
python run.py
python scripts/smoke_check.py
```

Large local folder `PRODUCT IMAGES/` (~692 MB) is gitignored; safe to archive after confirming Cloudinary has all product images.

### Prerequisites

- Python 3.11+
- PostgreSQL (Neon or local — see `.env`)

---

## Credentials & access

### Store URLs (local)

| Page | URL |
|------|-----|
| Home | http://127.0.0.1:8000/ |
| Products | http://127.0.0.1:8000/products.html |
| Basket | http://127.0.0.1:8000/basket.html |
| Sign in | http://127.0.0.1:8000/login.html |
| Sign up | http://127.0.0.1:8000/signup.html |
| My account | http://127.0.0.1:8000/account.html |
| Admin portal | http://127.0.0.1:8000/admin |
| API docs | http://127.0.0.1:8000/docs |

### Admin account

Sign in at **http://127.0.0.1:8000/login.html** using either field below as the login identifier:

| Field | Value |
|-------|--------|
| **Username** | `admin` |
| **Email** | `gmsworldfood@gmail.com` |
| **Password** | `Gowthami09` |
| **Role** | `admin` |

After sign-in you land on the same site as customers. Use **Manage store** in the account menu (or open `/admin`) for catalog and site settings.

### Customer accounts

Customers **self-register** at http://127.0.0.1:8000/signup.html. There is no default customer username/password.

| Field | Rules |
|-------|--------|
| **Email** | Valid email (unique) |
| **Phone** | Country code + local number |
| **Password** | Min 8 chars, upper, lower, number, special character |

Example test password format: `Test@1234`

After sign-in, everyone lands on the home page. The header account menu shows their name; customers get **My Profile**, and admins also get **Manage store**.

### Environment (`.env`)

Copy `.env.example` to `.env` and fill in your values. **Do not commit `.env`.**

| Variable | Purpose |
|----------|---------|
| `APP_HOST` / `APP_PORT` | Server bind address (default `127.0.0.1:8000`) |
| `SECRET_KEY` | Session signing secret |
| `SESSION_EXPIRE_MINUTES` | Login session lifetime (default 10080 = 7 days) |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSL` | PostgreSQL (e.g. Neon) |
| `CLOUDINARY_*` | Product/category image hosting |
| `CORS_ORIGINS` | Allowed frontend origins |

### Store contact (public)

| Item | Value |
|------|--------|
| **Phone** | +44 7802617847 |
| **WhatsApp** | +44 7802617847 |
| **Address** | 88–90 High Street, West Drayton UB7 7DS |

### Browser session keys (dev reference)

| Key | Storage | Used for |
|-----|---------|----------|
| `gms_customer_token_v1` / `gms_customer_user_v1` | sessionStorage | Storefront customer (and admin when signed in via login page) |
| `gms_admin_token_v2` / `gms_admin_user_v2` | sessionStorage | Admin portal |
| `gms_basket_v1` | localStorage | Guest/customer basket items |

---

## Architecture notes

- **Frontend** loads catalog via split endpoints (`/api/v1/catalog/metadata`, `products-bulk`, `home-products`) and may still use `bootstrap` where needed.
- **Filtering** is client-side on the cached `ALL_PRODUCTS[]` array.
- **Guest basket** uses `localStorage` (`gms_basket_v1:guest`). Signed-in users get a per-account basket stored in Neon (`user_cart_items`) and cached as `gms_basket_v1:u:<userId>`.
- **Coupons** stored in `site_settings` (`setting_key = coupons`).
- **Images** served from Cloudinary URLs (admin upload) or `/uploads/products/`.

## API endpoints

### Catalog

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/catalog/bootstrap` | Full catalog bundle (legacy/init) |
| GET | `/api/v1/catalog/metadata` | Categories, subcategories, site metadata |
| GET | `/api/v1/catalog/products-bulk` | All active products (large payload) |
| GET | `/api/v1/catalog/home-products` | Home-page flagged products only |
| GET | `/api/v1/catalog/cart-products` | Product details for basket IDs |
| GET | `/api/v1/categories` | Category stats |
| GET | `/api/v1/categories/{id}` | Single category |
| GET | `/api/v1/subcategories` | Subcategory stats (`?category_id=`) |
| GET | `/api/v1/products` | Paginated/filterable products |
| GET | `/api/v1/products/featured` | Featured products |
| GET | `/api/v1/products/best-sellers` | Best sellers |
| GET | `/api/v1/products/new-arrivals` | New arrivals |
| GET | `/api/v1/products/hot-offers` | Hot offers |
| GET | `/api/v1/products/exclusive` | Exclusive products |
| GET | `/api/v1/products/{id}` | Product detail |
| GET | `/api/v1/products/{id}/images` | Product images |
| GET | `/api/v1/banners` | Promotion banners |
| GET | `/api/v1/testimonials` | Customer testimonials |

### Auth

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Register |
| POST | `/api/v1/auth/login` | Login (Bearer token) |
| GET | `/api/v1/auth/me` | Current user |
| POST | `/api/v1/auth/logout` | End session |

### Newsletter

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/newsletter/subscribe` | Subscribe email |

### Admin (`role = admin`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/admin/stats` | Dashboard stats |
| GET/POST/PUT/DELETE | `/api/v1/admin/categories` | Categories |
| GET/POST | `/api/v1/admin/subcategories` | Subcategories |
| GET/POST/PUT/DELETE | `/api/v1/admin/products` | Products |
| GET/POST/PUT/DELETE | `/api/v1/admin/banners` | Banners |
| GET/PUT | `/api/v1/admin/coupons` | Coupon management |
| GET | `/api/v1/coupons/active` | Active coupons (basket) |

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Health check |
