import base64
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from models.job import Job
from parser.job_parser import extract_jobs_from_html


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

BASE_DIR = Path(__file__).resolve().parent

CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"

RAW_JOBS_FILE = BASE_DIR / "jobs_raw.json"

DATA_DIR = BASE_DIR / "data"
COLLECTOR_STATE_FILE = DATA_DIR / "collector_state.json"

MAX_EMAILS = 100


def authenticate() -> Credentials:
    """
    Autentica o usuário no Google e retorna as credenciais
    necessárias para acessar a Gmail API.
    """
    credentials = None

    if TOKEN_FILE.exists():
        credentials = Credentials.from_authorized_user_file(
            TOKEN_FILE,
            SCOPES,
        )

    if not credentials or not credentials.valid:
        if (
            credentials
            and credentials.expired
            and credentials.refresh_token
        ):
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


def find_label_id(
    service: Any,
    label_name: str,
) -> str | None:
    """
    Procura uma label pelo nome e retorna o ID interno
    utilizado pela Gmail API.
    """
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


def extract_html(payload: dict) -> str | None:
    """
    Procura a parte HTML dentro da estrutura do email,
    decodifica o conteúdo e retorna uma string.
    """
    mime_type = payload.get("mimeType")
    body_data = payload.get("body", {}).get("data")

    if mime_type == "text/html" and body_data:
        decoded = base64.urlsafe_b64decode(body_data)

        return decoded.decode(
            "utf-8",
            errors="replace",
        )

    for part in payload.get("parts", []):
        html = extract_html(part)

        if html:
            return html

    return None


def load_collector_state() -> dict:
    """
    Carrega os IDs dos emails que já foram processados.
    """
    if not COLLECTOR_STATE_FILE.exists():
        return {
            "processed_email_ids": [],
        }

    try:
        state = json.loads(
            COLLECTOR_STATE_FILE.read_text(
                encoding="utf-8",
            )
        )

    except (json.JSONDecodeError, OSError):
        return {
            "processed_email_ids": [],
        }

    processed_ids = state.get(
        "processed_email_ids",
        [],
    )

    if not isinstance(processed_ids, list):
        processed_ids = []

    return {
        "processed_email_ids": processed_ids,
    }


def save_collector_state(
    processed_email_ids: set[str],
) -> None:
    """
    Salva os IDs dos emails processados com sucesso.
    """
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    state = {
        "processed_email_ids": sorted(
            processed_email_ids
        ),
    }

    COLLECTOR_STATE_FILE.write_text(
        json.dumps(
            state,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_existing_jobs() -> dict[str, Job]:
    """
    Carrega as vagas que já existem em jobs_raw.json.
    """
    if not RAW_JOBS_FILE.exists():
        return {}

    try:
        jobs_data = json.loads(
            RAW_JOBS_FILE.read_text(
                encoding="utf-8",
            )
        )

    except (json.JSONDecodeError, OSError):
        return {}

    jobs: dict[str, Job] = {}

    for job_data in jobs_data:
        try:
            job = Job(**job_data)
            jobs[job.id] = job

        except (TypeError, KeyError):
            continue

    return jobs


def save_jobs(
    jobs: dict[str, Job],
) -> None:
    """
    Salva todas as vagas conhecidas em jobs_raw.json.
    """
    jobs_data = [
        asdict(job)
        for job in jobs.values()
    ]

    RAW_JOBS_FILE.write_text(
        json.dumps(
            jobs_data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def list_email_references(
    service: Any,
    label_id: str,
) -> list[dict]:
    """
    Busca referências dos emails existentes na label.

    Esta função não abre ainda o conteúdo completo dos emails.
    """
    response = (
        service.users()
        .messages()
        .list(
            userId="me",
            labelIds=[label_id],
            maxResults=MAX_EMAILS,
        )
        .execute()
    )

    return response.get(
        "messages",
        [],
    )


def should_replace_job(
    current_job: Job | None,
    new_job: Job,
) -> bool:
    """
    Decide se uma vaga recém-extraída possui dados melhores
    que a versão já armazenada.
    """
    if current_job is None:
        return True

    return len(new_job.raw_text) > len(
        current_job.raw_text
    )


def collect_jobs(
    service: Any,
    label_id: str,
    verbose: bool = True,
) -> dict:
    """
    Processa somente emails ainda desconhecidos.

    Depois:
    - extrai vagas;
    - deduplica pelo LinkedIn Job ID;
    - combina com jobs_raw.json;
    - salva o estado dos emails processados.
    """
    state = load_collector_state()

    processed_email_ids = set(
        state["processed_email_ids"]
    )

    existing_jobs = load_existing_jobs()

    message_references = list_email_references(
        service=service,
        label_id=label_id,
    )

    new_message_references = [
        message
        for message in message_references
        if message["id"] not in processed_email_ids
    ]

    emails_processed_now = 0
    emails_without_html = 0

    jobs_found_now = 0
    new_jobs_count = 0
    updated_jobs_count = 0
    duplicated_jobs_count = 0

    for message_reference in new_message_references:
        message_id = message_reference["id"]

        try:
            message = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=message_id,
                    format="full",
                )
                .execute()
            )

            html = extract_html(
                message["payload"]
            )

            if not html:
                emails_without_html += 1
                processed_email_ids.add(message_id)
                emails_processed_now += 1
                continue

            jobs_from_email = extract_jobs_from_html(
                html
            )

            jobs_found_now += len(
                jobs_from_email
            )

            for job_id, new_job in jobs_from_email.items():
                current_job = existing_jobs.get(
                    job_id
                )

                if current_job is None:
                    existing_jobs[job_id] = new_job
                    new_jobs_count += 1

                elif should_replace_job(
                    current_job=current_job,
                    new_job=new_job,
                ):
                    existing_jobs[job_id] = new_job
                    updated_jobs_count += 1

                else:
                    duplicated_jobs_count += 1

            # Primeiro persistimos as vagas.
            save_jobs(existing_jobs)

            # Somente depois marcamos o email como processado.
            processed_email_ids.add(message_id)

            save_collector_state(
                processed_email_ids
            )

            emails_processed_now += 1

        except Exception as error:
            print(
                "\nFalha ao processar email "
                f"{message_id}: {error}"
            )

            # O email não é marcado como processado.
            # Assim será tentado novamente na próxima execução.
            continue

    # Garante a existência dos arquivos mesmo quando não há emails novos.
    save_jobs(existing_jobs)

    save_collector_state(
        processed_email_ids
    )

    print("\n" + "=" * 60)
    print("COLETA INCREMENTAL")
    print("=" * 60)

    print(
        f"Emails encontrados na label: "
        f"{len(message_references)}"
    )

    print(
        f"Emails já processados:       "
        f"{len(message_references) - len(new_message_references)}"
    )

    print(
        f"Emails novos encontrados:    "
        f"{len(new_message_references)}"
    )

    print(
        f"Emails processados agora:    "
        f"{emails_processed_now}"
    )

    print(
        f"Emails sem HTML:              "
        f"{emails_without_html}"
    )

    print(
        f"Vagas encontradas agora:      "
        f"{jobs_found_now}"
    )

    print(
        f"Vagas realmente novas:        "
        f"{new_jobs_count}"
    )

    print(
        f"Vagas atualizadas:            "
        f"{updated_jobs_count}"
    )

    print(
        f"Vagas duplicadas ignoradas:   "
        f"{duplicated_jobs_count}"
    )

    print(
        f"Total armazenado:             "
        f"{len(existing_jobs)}"
    )

    print("=" * 60)

    if verbose and new_jobs_count > 0:
        print("\nNovas vagas:\n")

        for job in existing_jobs.values():
            print(f"ID: {job.id}")
            print(f"Título: {job.title}")
            print(f"Empresa: {job.company}")
            print(f"URL: {job.url}")
            print("-" * 60)

    print(f"\nVagas salvas em: {RAW_JOBS_FILE}")
    print(f"Estado salvo em: {COLLECTOR_STATE_FILE}")

    return {
        "jobs": [
            asdict(job)
            for job in existing_jobs.values()
        ],
        "new_jobs_count": new_jobs_count,
        "updated_jobs_count": updated_jobs_count,
        "duplicate_jobs_count": duplicated_jobs_count,
        "emails_found": len(message_references),
        "new_emails": len(new_message_references),
        "processed_emails": emails_processed_now,
        "output_file": RAW_JOBS_FILE,
        "state_file": COLLECTOR_STATE_FILE,
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