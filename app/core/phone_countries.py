"""Phone country dial codes for customer registration."""

PHONE_DIAL_CODES: dict[str, str] = {
    "GB": "+44",
    "IE": "+353",
    "IN": "+91",
    "US": "+1",
    "CA": "+1",
    "AU": "+61",
    "AE": "+971",
    "PK": "+92",
    "BD": "+880",
    "LK": "+94",
    "FR": "+33",
    "DE": "+49",
    "IT": "+39",
    "ES": "+34",
    "NL": "+31",
}


def normalize_digits(value: str) -> str:
    return "".join(ch for ch in (value or "").strip() if ch.isdigit())


def build_international_phone(country: str, phone: str) -> str:
    raw = (phone or "").strip()
    if raw.startswith("+"):
        cleaned = "+" + normalize_digits(raw)
        return cleaned if len(cleaned) > 4 else raw

    country = (country or "GB").upper()
    dial = PHONE_DIAL_CODES.get(country, "+44")
    local = normalize_digits(raw)
    if country == "GB" and local.startswith("0"):
        local = local[1:]
    return f"{dial}{local}"
