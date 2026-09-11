import re


_ALIASES = {
    "product ops": "Product Operations",
    "product operations": "Product Operations",
    "customer ops": "Customer Operations",
    "customer operations": "Customer Operations",
}


def normalize_role_family(value) -> str:
    label = re.sub(r"\s+", " ", str(value or "").strip())
    label = re.sub(r"[.;:,]+$", "", label).strip()
    if not label:
        return ""
    return _ALIASES.get(label.casefold(), label)


def role_family_key(value) -> str:
    return normalize_role_family(value).casefold()
