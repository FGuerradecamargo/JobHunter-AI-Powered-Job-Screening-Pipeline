import os

import requests
from dotenv import load_dotenv

from models.job import Job
from services.job_sources.base_job_source import JobSource


class JoobleJobSource(JobSource):

    def __init__(self) -> None:
        load_dotenv()

        self.api_key = os.getenv("JOOBLE_API_KEY")

        if not self.api_key:
            raise ValueError("JOOBLE_API_KEY was not found.")

    def search(
        self,
        keywords: str,
        location: str,
        page: int = 1,
        results_per_page: int = 20,
    ) -> list[Job]:

        url = (
            "https://jooble.org/api/"
            f"{self.api_key}"
        )

        response = requests.post(
            url,
            json={
                "keywords": keywords,
                "location": location,
                "page": str(page),
                "ResultOnPage": results_per_page,
            },
            timeout=30,
        )

        response.raise_for_status()
        data = response.json()

        jobs = []

        for item in data.get("jobs", []):
            job_id = str(item.get("id", "")).strip()

            if not job_id:
                continue

            title = (
                item.get("title") or ""
            ).strip()

            company = (
                item.get("company") or ""
            ).strip()

            job_location = (
                item.get("location") or location
            ).strip()

            description = (
                item.get("snippet") or ""
            ).strip()

            job_url = (
                item.get("link") or ""
            ).strip()

            salary = (
                item.get("salary") or None
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
                    id=f"jooble:{job_id}",
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
