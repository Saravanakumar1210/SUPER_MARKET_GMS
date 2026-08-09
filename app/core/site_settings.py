"""Public storefront site settings (header, footer, contact, about)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SiteSetting

DEFAULT_SITE_SETTINGS: dict[str, str] = {
    "store_name": "GMS World Foods Ltd",
    "store_tagline": "Wholesale & Retail",
    "store_phone": "+44 7802617847",
    "whatsapp_number": "447802617847",
    "contact_email": "gmsworldfood@gmail.com",
    "store_address": "88–90 High Street",
    "store_city": "West Drayton",
    "store_postcode": "UB7 7DS",
    "opening_hours": "Open Daily — Mon to Sun",
    "opening_hours_mon_fri": "8:00am – 9:00pm",
    "opening_hours_saturday": "8:00am – 9:00pm",
    "opening_hours_sunday": "9:00am – 8:00pm",
    "footer_desc": (
        "Your local world foods specialist in West Drayton — stocking quality groceries "
        "from across the globe for retail and wholesale customers."
    ),
    "home_about_teaser": (
        "Located at 88–90 High Street, West Drayton, GMS World Foods Ltd is a dedicated "
        "world foods wholesaler and retailer serving local communities and trade customers "
        "across the region."
    ),
    "home_about_teaser_extra": (
        "We stock an extensive catalog spanning fresh vegetables, dry goods, rice, confectionery, "
        "soft drinks, household essentials, and a wide variety of international specialty products."
    ),
    "about_us_text": (
        "GMS World Foods Ltd is a dedicated world foods wholesale and retail business located "
        "at 88–90 High Street, West Drayton, UB7 7DS. We are committed to connecting our "
        "community with quality products sourced from around the globe.\n\n"
        "We maintain an extensive catalog spanning fresh produce, dry goods, rice, beverages, "
        "confectionery, and household essentials — ensuring that our customers and trade partners "
        "always find exactly what they need.\n\n"
        "From everyday pantry staples to specialty international items, our range reflects the "
        "diverse needs of the communities we proudly serve in West Drayton and the surrounding area."
    ),
    "delivery_area": "West Drayton & surrounding areas",
    "maps_embed_url": (
        "https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d2482.560862452041!2d-0.47435!3d51.50627!"
        "2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x48766b5e85f4d061%3A0x5c3b5db89cd4f3f2!"
        "2s88-90%20High%20St%2C%20West%20Drayton%20UB7%207DS!5e0!3m2!1sen!2suk!4v1718000000000!5m2!1sen!2suk"
    ),
    "social_facebook": "",
    "social_instagram": "",
    "social_twitter": "",
    "store_logo_url": "",
    "newsletter_background_url": "",
    "newsletter_visual_url": "",
    "store_hero_image_url": "",
    "store_gallery_urls": "[]",
}

SITE_SETTING_KEYS = frozenset(DEFAULT_SITE_SETTINGS.keys())


async def load_public_site_settings(db: AsyncSession) -> dict[str, str]:
    result = await db.execute(
        select(SiteSetting).where(SiteSetting.setting_key.in_(SITE_SETTING_KEYS))
    )
    stored = {
        row.setting_key: row.setting_value
        for row in result.scalars()
        if row.setting_value is not None and str(row.setting_value).strip() != ""
    }
    return {**DEFAULT_SITE_SETTINGS, **stored}
