import hashlib
import json
from dataclasses import asdict

from models.career_development_context import (
    CareerDevelopmentContext,
)


def build_career_development_signature(
    context: CareerDevelopmentContext,
) -> str:
    payload = json.dumps(
        asdict(context),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()
