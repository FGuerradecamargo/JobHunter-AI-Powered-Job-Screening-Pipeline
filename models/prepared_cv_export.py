from dataclasses import dataclass


@dataclass(frozen=True)
class PreparedCVExport:
    data: bytes
    filename: str
    mime_type: str
