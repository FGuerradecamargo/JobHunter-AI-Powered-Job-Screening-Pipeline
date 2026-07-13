from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"


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

        TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")

    return credentials


def find_label_id(service, label_name: str) -> str | None:
    response = service.users().labels().list(userId="me").execute()

    for label in response.get("labels", []):
        if label["name"] == label_name:
            return label["id"]

    return None


def list_jobhunter_emails(service, label_id: str) -> None:
    response = (
        service.users()
        .messages()
        .list(
            userId="me",
            labelIds=[label_id],
            maxResults=10,
        )
        .execute()
    )

    messages = response.get("messages", [])

    if not messages:
        print("Nenhum e-mail encontrado com a label JobHunter.")
        return

    print(f"{len(messages)} e-mail(s) encontrado(s):\n")

    for message in messages:
        email = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=message["id"],
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            )
            .execute()
        )

        headers = {
            header["name"]: header["value"]
            for header in email["payload"].get("headers", [])
        }

        print(f"Subject: {headers.get('Subject', 'Sem assunto')}")
        print(f"From: {headers.get('From', 'Remetente desconhecido')}")
        print(f"Date: {headers.get('Date', 'Data desconhecida')}")
        print("-" * 60)


def main() -> None:
    credentials = authenticate()
    service = build("gmail", "v1", credentials=credentials)

    label_id = find_label_id(service, "JobHunter")

    if not label_id:
        print("Label JobHunter não encontrada.")
        return

    list_jobhunter_emails(service, label_id)


if __name__ == "__main__":
    main()