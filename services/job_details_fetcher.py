import requests
import logging
from services.provider_failure import log_failure, provider_boundary, ProviderFailure
from bs4 import BeautifulSoup


JOB_DESCRIPTION_SELECTOR = ".show-more-less-html__markup"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/138.0 Safari/537.36"
    )
}


def extract_job_description(html: str) -> str | None:
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    description_node = soup.select_one(
        JOB_DESCRIPTION_SELECTOR
    )

    if not description_node:
        return None

    return description_node.get_text(
        "\n",
        strip=True,
    )


def fetch_job_description(url: str) -> str | None:
    try:
        with provider_boundary('job_enrichment'):
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=15,
            )
            response.raise_for_status()

    except ProviderFailure as error:
        log_failure(logging.getLogger(__name__), 'job_enrichment', error)
        return None

    description = extract_job_description(
        response.text
    )

    if description is None:
        logging.getLogger(__name__).info('job_description_unavailable')

    return description


if __name__ == "__main__":
    url = "https://www.linkedin.com/jobs/view/4438277162"

    description = fetch_job_description(url)

    if description is None:
        print("Descrição não encontrada.")
    else:
        print(description[:2000])
