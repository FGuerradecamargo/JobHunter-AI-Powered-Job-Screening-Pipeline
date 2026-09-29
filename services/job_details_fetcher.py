import requests
import logging
import time
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

JOB_DESCRIPTION_RETRY_STATUSES = {
    429,
    503,
}

JOB_DESCRIPTION_MAX_ATTEMPTS = 2
JOB_DESCRIPTION_MAX_RETRY_AFTER_SECONDS = 5


def _retry_delay(
    response,
    attempt: int,
) -> float | None:
    retry_after = str(
        response.headers.get(
            "Retry-After",
            "",
        )
        or ""
    ).strip()

    if retry_after:
        if not retry_after.isdigit():
            return None

        delay = int(
            retry_after
        )

        if (
            delay
            > JOB_DESCRIPTION_MAX_RETRY_AFTER_SECONDS
        ):
            return None

        return float(
            delay
        )

    return 0.5 * (
        attempt + 1
    )


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
    response = None

    for attempt in range(
        JOB_DESCRIPTION_MAX_ATTEMPTS
    ):
        retry_delay = None

        try:
            with provider_boundary(
                "job_enrichment"
            ):
                response = requests.get(
                    url,
                    headers=HEADERS,
                    timeout=15,
                )

                if (
                    response.status_code
                    in JOB_DESCRIPTION_RETRY_STATUSES
                ):
                    retry_delay = _retry_delay(
                        response,
                        attempt,
                    )

                    if (
                        attempt + 1
                        >= JOB_DESCRIPTION_MAX_ATTEMPTS
                        or retry_delay is None
                    ):
                        response.raise_for_status()

                else:
                    response.raise_for_status()

        except ProviderFailure as error:
            log_failure(
                logging.getLogger(__name__),
                "job_enrichment",
                error,
            )

            return None

        if retry_delay is None:
            break

        time.sleep(
            retry_delay
        )

    if response is None:
        return None

    description = extract_job_description(
        response.text
    )

    if description is None:
        logging.getLogger(__name__).info(
            "job_description_unavailable"
        )

    return description


if __name__ == "__main__":
    url = "https://www.linkedin.com/jobs/view/4438277162"

    description = fetch_job_description(url)

    if description is None:
        print("Descrição não encontrada.")
    else:
        print(description[:2000])
