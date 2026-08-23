import os

import requests
from dotenv import load_dotenv

from models.job import Job
from services.job_sources.base_job_source import JobSource


class AdzunaJobSource(JobSource):

    def __init__(self, country: str = "ie") -> None:
        load_dotenv()

        self.app_id = os.getenv("ADZUNA_APP_ID")
        self.app_key = os.getenv("ADZUNA_APP_KEY")
        self.country = country

        if not self.app_id:
            raise ValueError("ADZUNA_APP_ID was not found.")

        if not self.app_key:
            raise ValueError("ADZUNA_APP_KEY was not found.")

    def search(
        self,
        keywords: str,
        location: str,
        page: int = 1,
        results_per_page: int = 20,
    ) -> list[Job]:

        url = (
            "https://api.adzuna.com/"
            f"v1/api/jobs/{self.country}/search/{page}"
        )

        response = requests.get(
            url,
            params={
                "app_id": self.app_id,
                "app_key": self.app_key,
                "what": keywords,
                "where": location,
                "results_per_page": results_per_page,
            },
            timeout=30,
        )

        response.raise_for_status()
        data = response.json()

        jobs = []

        for item in data.get("results", []):
            job_id = str(item.get("id", "")).strip()

            if not job_id:
                continue

            title = (item.get("title") or "").strip()

            company = (
                (item.get("company") or {})
                .get("display_name", "")
                .strip()
            )

            job_location = (
                (item.get("location") or {})
                .get("display_name", "")
                .strip()
            )

            description = (
                item.get("description") or ""
            ).strip()

            job_url = (
                item.get("redirect_url") or ""
            ).strip()

            salary_min = item.get("salary_min")
            salary_max = item.get("salary_max")

            salary = None

            if salary_min is not None or salary_max is not None:
                values = [
                    float(value)
                    for value in (
                        salary_min,
                        salary_max,
                    )
                    if value is not None
                ]

                if len(values) == 1:
                    salary = (
                        f"GBP {values[0]:,.0f}"
                    )
                elif (
                    len(values) == 2
                    and values[0] == values[1]
                ):
                    salary = (
                        f"GBP {values[0]:,.0f}"
                    )
                else:
                    salary = (
                        "GBP "
                        + " - ".join(
                            f"{value:,.0f}"
                            for value in values
                        )
                    )

            raw_text = "\n".join(
                part
                for part in (
                    title,
                    company,
                    job_location,
                    description,
                )
                if part
            )

            remote_text = (
                f"{title} {job_location} {description}"
            ).lower()

            jobs.append(
                Job(
                    id=f"adzuna:{job_id}",
                    raw_text=raw_text,
                    url=job_url,
                    title=title or None,
                    company=company or None,
                    location=job_location or None,
                    remote=True if "remote" in remote_text else None,
                    salary=salary,
                    easy_apply=False,
                    description=description or None,
                )
            )

        return jobs
