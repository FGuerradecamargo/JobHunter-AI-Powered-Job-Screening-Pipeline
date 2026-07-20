import json
from pathlib import Path

from services.report_builder import ReportBuilder


INPUT_FILE = Path("jobs_ai_recommended.json")
OUTPUT_FILE = Path("job_report.md")


def main() -> None:
    with INPUT_FILE.open("r", encoding="utf-8") as file:
        recommendations = json.load(file)

    report = ReportBuilder().build(recommendations)

    OUTPUT_FILE.write_text(
        report,
        encoding="utf-8",
    )

    print(
        f"Report generated successfully: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
