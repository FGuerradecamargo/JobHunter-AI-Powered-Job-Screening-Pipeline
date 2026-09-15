from services.job_sources.board_http import BoardError
from services.job_sources.employer_board import BoardJob, EmployerBoard, body, posting_url, published_date, text


class AshbyJobSource(EmployerBoard):
    def __init__(self, source, company_name, http=None):
        super().__init__(source, company_name, "ashby", http)
        self.endpoint = f"https://api.ashbyhq.com/posting-api/job-board/{self.board}"

    def normalize(self, record):
        if record.get("isListed") is not True:
            raise ValueError("Not a publicly listed posting.")
        url, identifier = posting_url(record.get("jobUrl"), "jobs.ashbyhq.com", self.board)
        title = text(record.get("title"))
        if not title:
            raise ValueError("Missing title.")
        locations = [text(record.get("location"))]
        extra = record.get("secondaryLocations")
        if isinstance(extra, list):
            locations.extend(text(x.get("location")) for x in extra if isinstance(x, dict))
        location = "; ".join(dict.fromkeys(x for x in locations if x)) or None
        description = body(record.get("descriptionPlain"), record.get("descriptionHtml"))
        remote = record.get("isRemote")
        if type(remote) is not bool:
            remote = None
        return BoardJob(
            id=f"{self.source_type}:{self.board}:{identifier}", title=title,
            company=self.company_name, url=url, location=location, remote=remote,
            description=description or None, published_at=published_date(record.get("publishedAt")),
            raw_text="\n".join(p for p in [title, self.company_name, location,
                                          text(record.get("workplaceType")), description] if p),
        )

    def search(self, keywords="", location="", page=1, results_per_page=20):
        self.validate_search(keywords, location, page, results_per_page)
        self.skipped_records = 0
        data = self.http.get_json(self.endpoint, params={})
        if not isinstance(data, dict) or data.get("apiVersion") != "1" or not isinstance(data.get("jobs"), list):
            raise BoardError("response_shape")
        if len(data["jobs"]) > self.MAX_JOBS:
            raise BoardError("board_too_large")
        jobs = {}
        self.parse_records(data["jobs"], jobs)
        return list(jobs.values())
