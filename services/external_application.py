from urllib.parse import urlsplit, urlunsplit


def external_application_url(value: str) -> str:
    """
    WorkPilot redirects; it does not submit the application.
    """
    value = str(value or "").strip()
    if any(ord(char) < 32 for char in value) or "\\" in value:
        raise ValueError("A valid external application URL is required.")
    parsed = urlsplit(value)
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError(
            "A valid external application URL is required."
        )
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc,
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )
