# Scripts

Maintenance utilities. Run from the project root. These do **not** serve the website.

```
scripts/
├── smoke_check.py          # HTTP smoke check against a running server
├── _bootstrap.py           # Shared PROJECT_ROOT helper
├── uploads/                # Push local source images → Cloudinary / DB
├── cloudinary/             # Audit / reorganize Cloudinary folders
├── catalog/                # Category image layout + kitchen-culture seeding
└── maintenance/            # One-off DB checks, cache invalidate, progress
```

## Common commands

```cmd
python scripts/smoke_check.py
python scripts/uploads/upload_product_images.py --dry-run
python scripts/uploads/upload_category_images.py
python scripts/uploads/upload_hero_banners.py
python scripts/uploads/upload_culture_banners.py
python scripts/catalog/seed_kitchen_cultures.py
python scripts/catalog/check_cultures.py
python scripts/maintenance/invalidate_cache.py
python scripts/maintenance/status_check.py
```

Source images live under `data/source-images/`. Bulk product photos live in the gitignored `PRODUCT IMAGES/` folder at the repo root.
