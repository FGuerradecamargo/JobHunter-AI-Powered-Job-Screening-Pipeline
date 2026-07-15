from models.job import Job
from services.job_details_fetcher import fetch_job_description


class JobEnricher:
    def enrich(self, job: Job) -> Job:
        job.description = fetch_job_description(job.url)
        return job


if __name__ == "__main__":
    job = Job(
        id="4438277162",
        raw_text="Automation Engineer",
        url="https://www.linkedin.com/jobs/view/4438277162",
        title="Automation Engineer",
        company="European Tech Recruit",
        location="Limerick Metropolitan Area",
    )

    enricher = JobEnricher()
    enricher.enrich(job)

    if job.description is None:
        print("Descrição não encontrada.")
    else:
        print(job.title)
        print(f"{len(job.description)} caracteres")
        print(job.description[:500])