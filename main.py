import base64
import json
from dataclasses import asdict
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from parser.job_parser import extract_jobs_from_html


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"


# Autentica o usuário no Google e retorna as credenciais necessárias para acessar a Gmail API.
def authenticate() -> Credentials:
    credentials = None

    if TOKEN_FILE.exists():
        credentials = Credentials.from_authorized_user_file(
            TOKEN_FILE,
            SCOPES,
        )

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE,
                SCOPES,
            )
            credentials = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(
            credentials.to_json(),
            encoding="utf-8",
        )

    return credentials


# Procura uma label pelo nome e retorna o ID usado internamente pela Gmail API.
def find_label_id(service, label_name: str) -> str | None:
    response = (
        service.users()
        .labels()
        .list(userId="me")
        .execute()
    )

    for label in response.get("labels", []):
        if label["name"] == label_name:
            return label["id"]

    return None


# Procura a parte HTML dentro da estrutura do e-mail, decodifica o conteúdo e retorna uma string.
def extract_html(payload: dict) -> str | None:
    mime_type = payload.get("mimeType")
    body_data = payload.get("body", {}).get("data")

    if mime_type == "text/html" and body_data:
        decoded = base64.urlsafe_b64decode(body_data)
        return decoded.decode("utf-8")

    for part in payload.get("parts", []):
        html = extract_html(part)

        if html:
            return html

    return None


# Busca os e-mails da label, extrai vagas únicas e salva os dados brutos em JSON.
# Busca os e-mails da label, extrai vagas únicas e salva os dados brutos em JSON.
def collect_jobs(
    service,
    label_id: str,
    verbose: bool = True,
) -> dict:
    output_jobs = BASE_DIR / "jobs_raw.json"

    response = (
        service.users()
        .messages()
        .list(
            userId="me",
            labelIds=[label_id],
            maxResults=6,
        )
        .execute()
    )

    messages = response.get("messages", [])

    if not messages:
        raise RuntimeError(
            "Nenhum e-mail encontrado na label JobHunter."
        )

    job_links = {}

    for message_reference in messages:
        message = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=message_reference["id"],
                format="full",
            )
            .execute()
        )

        html = extract_html(message["payload"])

        if not html:
            continue

        jobs_from_email = extract_jobs_from_html(html)

        for job_id, job in jobs_from_email.items():
            if (
                job_id not in job_links
                or len(job.raw_text) > len(job_links[job_id].raw_text)
            ):
                job_links[job_id] = job

    jobs_data = [
        asdict(job)
        for job in job_links.values()
    ]

    if verbose:
        print(f"{len(job_links)} vagas únicas encontradas:\n")

        for job in job_links.values():
            print(f"ID: {job.id}")
            print(f"Título: {job.title}")
            print(f"Texto bruto: {job.raw_text}")
            print(f"URL: {job.url}")
            print("-" * 60)

    with open(
        output_jobs,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            jobs_data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print(f"Vagas salvas em: {output_jobs}")

    return {
        "jobs": jobs_data,
        "output_file": output_jobs,
    }


def main(
    verbose: bool = True,
) -> dict:
    credentials = authenticate()

    service = build(
        "gmail",
        "v1",
        credentials=credentials,
    )

    label_id = find_label_id(
        service,
        "JobHunter",
    )

    if not label_id:
        raise RuntimeError(
            "Label JobHunter não encontrada."
        )

    return collect_jobs(
        service=service,
        label_id=label_id,
        verbose=verbose,
    )


if __name__ == "__main__":
    main()