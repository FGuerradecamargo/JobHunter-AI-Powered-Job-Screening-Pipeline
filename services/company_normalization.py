from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit


def company_name(value: str) -> tuple[str, str]:
    if not isinstance(value, str):
        raise ValueError("Company name is required.")
    name = " ".join(unicodedata.normalize("NFC", value).translate(
        str.maketrans({"\u2019": "'", "\u2018": "'"})
    ).split())
    if not name or len(name) > 250:
        raise ValueError("Company name must contain 1 to 250 characters.")
    return name, name.casefold()


def public_careers_url(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    try:
        parts = urlsplit(value.strip())
        port = parts.port
    except ValueError:
        raise ValueError("Careers URL is invalid.") from None
    if (
        parts.scheme.lower() not in {"https", "http"} or not parts.hostname
        or parts.username or parts.password or parts.query or parts.fragment
        or port is not None
        or any(c.isspace() for c in value.strip())
    ):
        raise ValueError("Use a public careers URL without credentials or query parameters.")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, "", ""))


def company_domain(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    domain = value.strip().lower().rstrip(".")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", domain) or ".." in domain:
        raise ValueError("Company domain is invalid.")
    return domain


def source_identifier(value: str, *, source_type: bool = False) -> str:
    value = str(value or "").strip()
    if source_type:
        value = value.lower()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value):
        raise ValueError("Source identifiers must be short public names.")
    return value
