from bs4 import BeautifulSoup

from models.job import Job


# Extrai vagas únicas do HTML de um alerta do LinkedIn.
def extract_jobs_from_html(html: str) -> dict[str, Job]:
    soup = BeautifulSoup(html, "html.parser")
    job_links: dict[str, Job] = {}

    for link in soup.find_all("a"):
        href = link.get("href")
        text = link.get_text(" ", strip=True)

        if not href or "/jobs/view/" not in href:
            continue

        title_node = link.find(string=lambda value: value and value.strip())

        title = title_node.strip() if title_node else None

        if not text:
            continue

        company = None
        location = None

        details = link.find("p", class_="text-system-gray-100")

        if details:
            details_text = details.get_text(" ", strip=True)

            if " · " in details_text:
                company, location = details_text.split(" · ", 1)

        #Object criation
        card_text = link.get_text(" ", strip=True)
        easy_apply = "Easy Apply" in card_text

        remote_text = f"{title} {location or ''}".lower()
        remote = "remote" in remote_text

        job_id = href.split("/jobs/view/")[1].split("?")[0]
        clean_url = f"https://www.linkedin.com/jobs/view/{job_id}"

        if (
            job_id not in job_links
            or len(title) > len(job_links[job_id].raw_text)
        ):
            job_links[job_id] = Job(
                id=job_id,
                raw_text=card_text,
                url=clean_url,
                title=title,
                company=company,
                location=location,
                easy_apply=easy_apply,
                remote=remote,
            )

    return job_links