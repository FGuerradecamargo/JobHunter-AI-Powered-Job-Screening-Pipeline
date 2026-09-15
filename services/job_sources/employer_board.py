from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit, urlunsplit

from models.company import CompanyJobSource
from models.job import Job
from services.company_normalization import source_identifier
from services.employer_provider_registry import employer_run_name
from services.job_observation import normalize_observation
from services.job_sources.board_http import BoardError, BoardHTTPClient


@dataclass
class BoardJob(Job):
    # Boundary-only field; existing ingestion intentionally does not persist it.
    published_at: datetime | None = None


def text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


class _BodyText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        elif tag in {"p", "div", "li", "br", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        elif tag in {"p", "div", "li"}:
            self.parts.append("\n")

    def handle_data(self, value):
        if not self.hidden:
            self.parts.append(value)


def body(plain, html) -> str:
    if text(plain):
        return text(plain)
    parser = _BodyText()
    try:
        parser.feed(text(html))
        parser.close()
    except (AssertionError, ValueError):
        raise ValueError("Invalid description markup.") from None
    return "\n".join(line.strip() for line in "".join(parser.parts).splitlines() if line.strip())


def published_date(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return date.astimezone(timezone.utc) if date.tzinfo else None
    except ValueError:
        return None


def posting_url(value, host: str, board: str) -> tuple[str, str]:
    value = text(value)
    if not value or any(c.isspace() or ord(c) < 32 for c in value) or "\\" in value:
        raise ValueError("Invalid posting URL.")
    parts = urlsplit(value)
    if parts.scheme not in {"https", "http"} or parts.netloc.lower() != host:
        raise ValueError("Invalid posting URL.")
    prefix = f"/{board}/"
    if not parts.path.startswith(prefix):
        raise ValueError("Invalid posting URL.")
    external_id = parts.path[len(prefix):]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", external_id):
        raise ValueError("Invalid posting URL.")
    return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment)), external_id


class EmployerBoard:
    MAX_JOBS = 10000
    MAX_TEXT = 20 * 1024 * 1024

    def __init__(self, source: CompanyJobSource, company_name: str, vendor: str, http=None):
        try:
            self.board = source_identifier(source.source_key)
            source_identifier(source.id)
        except ValueError:
            raise BoardError("invalid_source_key") from None
        if source.source_type != vendor or not source.enabled or not text(company_name):
            raise BoardError("invalid_source_setup")
        self.source_type = employer_run_name(source)
        self.company_name = company_name.strip()
        self.http = http if http is not None else BoardHTTPClient()
        self.skipped_records = 0

    def normalize(self, record: dict) -> BoardJob:
        raise NotImplementedError

    def parse_records(self, records: list, jobs: dict) -> None:
        for record in records:
            try:
                if not isinstance(record, dict):
                    raise ValueError("Invalid record.")
                job = self.normalize(record)
                jobs.setdefault(job.id, normalize_observation(job, self.source_type).job)
            except (ValueError, TypeError, KeyError):
                self.skipped_records += 1
        if len(jobs) > self.MAX_JOBS or sum(len(j.raw_text) for j in jobs.values()) > self.MAX_TEXT:
            raise BoardError("board_too_large")

    @staticmethod
    def validate_search(keywords, location, page, results_per_page):
        # Board configs request the complete feed, never candidate-specific queries.
        if keywords or location or page != 1 or type(results_per_page) is not int or results_per_page < 1:
            raise BoardError("unsupported_search")
