from bs4 import BeautifulSoup

from models.job import Job


def extract_jobs_from_html(
    html: str,
) -> dict[str, Job]:
    """
    Extrai vagas únicas do HTML de um alerta do LinkedIn.
    """
    if not html:
        return {}

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    job_links: dict[str, Job] = {}

    for link in soup.find_all("a"):
        href = link.get("href")
        text = link.get_text(
            " ",
            strip=True,
        )

        if not href:
            continue

        if "/jobs/view/" not in href:
            continue

        if not text:
            continue

        title_node = link.find(
            string=lambda value: (
                value
                and value.strip()
            )
        )

        title = (
            title_node.strip()
            if title_node
            else None
        )

        company = None
        location = None

        details = link.find(
            "p",
            class_="text-system-gray-100",
        )

        if details:
            details_text = details.get_text(
                " ",
                strip=True,
            )

            if " · " in details_text:
                company, location = (
                    details_text.split(
                        " · ",
                        1,
                    )
                )

        card_text = link.get_text(
            " ",
            strip=True,
        )

        easy_apply = (
            "Easy Apply" in card_text
        )

        remote_text = (
            f"{title or ''} "
            f"{location or ''}"
        ).lower()

        remote = (
            "remote" in remote_text
        )

        job_id_part = href.split(
            "/jobs/view/",
            1,
        )[1]

        job_id = (
            job_id_part
            .split("?", 1)[0]
            .split("/", 1)[0]
            .strip()
        )

        if not job_id:
            continue

        clean_url = (
            "https://www.linkedin.com/jobs/view/"
            f"{job_id}"
        )

        existing_job = job_links.get(
            job_id
        )

        if (
            existing_job is None
            or len(card_text)
            > len(existing_job.raw_text)
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