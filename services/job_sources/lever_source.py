from urllib.parse import urlsplit

from services.job_sources.board_http import BoardError
from services.job_sources.employer_board import BoardJob, EmployerBoard, body, posting_url, text


class LeverJobSource(EmployerBoard):
    MAX_PAGES = 100

    def __init__(self, source, company_name, http=None):
        super().__init__(source, company_name, "lever", http)
        # Only a known EU careers hostname can select the EU endpoint template.
        eu = urlsplit(source.careers_url or "").hostname == "jobs.eu.lever.co"
        self.job_host = "jobs.eu.lever.co" if eu else "jobs.lever.co"
        api_host = "api.eu.lever.co" if eu else "api.lever.co"
        self.endpoint = f"https://{api_host}/v0/postings/{self.board}"

    def normalize(self, record):
        url, url_id = posting_url(record.get("hostedUrl"), self.job_host, self.board)
        identifier, title = text(record.get("id")), text(record.get("text"))
        if identifier != url_id or not title:
            raise ValueError("Invalid posting identity.")
        categories = record.get("categories") or {}
        if not isinstance(categories, dict):
            raise ValueError("Invalid categories.")
        locations = [text(categories.get("location"))]
        extras = categories.get("allLocations")
        if isinstance(extras, list):
            locations.extend(text(value) for value in extras)
        location = "; ".join(dict.fromkeys(x for x in locations if x)) or None
        combined = body(record.get("descriptionPlain"), record.get("description"))
        parts = [combined] if combined else [
            body(record.get("openingPlain"), record.get("opening")),
            body(record.get("descriptionBodyPlain"), record.get("descriptionBody")),
        ]
        lists = record.get("lists")
        if isinstance(lists, list):
            for item in lists:
                if isinstance(item, dict):
                    parts.extend([text(item.get("text")), body(None, item.get("content"))])
        parts.append(body(record.get("additionalPlain"), record.get("additional")))
        description = "\n".join(p for p in parts if p)
        workplace = record.get("workplaceType")
        remote = True if workplace == "remote" else False if workplace == "on-site" else None
        return BoardJob(
            id=f"{self.source_type}:{self.board}:{identifier}", title=title,
            company=self.company_name, url=url, location=location, remote=remote,
            description=description or None,
            raw_text="\n".join(p for p in [title, self.company_name, location, text(workplace), description] if p),
        )

    def search(self, keywords="", location="", page=1, results_per_page=20):
        self.validate_search(keywords, location, page, results_per_page)
        self.skipped_records = 0
        jobs = {}
        page_size = min(results_per_page, 100)
        seen_ids = set()
        for index in range(self.MAX_PAGES):
            records = self.http.get_json(self.endpoint, params={
                "mode": "json", "skip": index * page_size, "limit": page_size,
            })
            if not isinstance(records, list) or len(records) > page_size:
                raise BoardError("response_shape")
            ids = {text(r.get("id")) for r in records if isinstance(r, dict)} - {""}
            if len(records) == page_size and ids and ids <= seen_ids:
                raise BoardError("pagination_stalled")
            seen_ids.update(ids)
            self.parse_records(records, jobs)
            if len(records) < page_size:
                return list(jobs.values())
        raise BoardError("pagination_limit")
