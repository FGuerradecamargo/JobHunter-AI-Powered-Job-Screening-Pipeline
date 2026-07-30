from parser.job_parser import (
    extract_jobs_from_html,
)


def test_extracts_linkedin_job():
    html = """
    <html>
        <body>
            <a
                href="https://www.linkedin.com/jobs/view/1234567890?trackingId=test"
            >
                <strong>
                    Technical Support Engineer
                </strong>

                <p class="text-system-gray-100">
                    Example Company · Limerick, Ireland
                </p>
            </a>
        </body>
    </html>
    """

    jobs = extract_jobs_from_html(html)

    assert "1234567890" in jobs

    job = jobs["1234567890"]

    assert (
        job.title
        == "Technical Support Engineer"
    )

    assert (
        job.url
        == (
            "https://www.linkedin.com/jobs/"
            "view/1234567890"
        )
    )