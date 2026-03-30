import os
import base64
from email.message import EmailMessage
from email.utils import parseaddr

from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def get_gmail_service():
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                # The saved refresh token is no longer usable; force a new OAuth flow.
                creds = None
                if os.path.exists("token.json"):
                    os.remove("token.json")
        else:
            creds = None

        if creds is None:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    return service


def fetch_recent_unread(limit=5):
    service = get_gmail_service()
    results = service.users().messages().list(
        userId="me",
        labelIds=["INBOX"],
        q="is:unread",
        maxResults=limit,
    ).execute()

    messages = results.get("messages", [])
    emails = []

    for m in messages:
        msg = service.users().messages().get(
            userId="me", id=m["id"], format="full"
        ).execute()

        headers = msg.get("payload", {}).get("headers", [])
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "")
        from_addr = next((h["value"] for h in headers if h["name"] == "From"), "")
        date = next((h["value"] for h in headers if h["name"] == "Date"), "")
        message_id = next((h["value"] for h in headers if h["name"].lower() == "message-id"), "")

        body = ""
        payload = msg.get("payload", {})
        parts = payload.get("parts", [])
        if parts:
            for part in parts:
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data")
                    if data:
                        body = base64.urlsafe_b64decode(data).decode("utf-8")
                        break
        else:
            data = payload.get("body", {}).get("data")
            if data:
                body = base64.urlsafe_b64decode(data).decode("utf-8")

        emails.append(
            {
                "id": m["id"],
                "threadId": msg.get("threadId"),
                "subject": subject,
                "from": from_addr,
                "from_email": extract_email_address(from_addr),
                "body": body,
                "date": date,
                "message_id": message_id,
            }
        )

    return emails


def extract_email_address(value: str) -> str:
    _, address = parseaddr(value or "")
    return address or (value or "").strip()


def mark_message_read(message_id: str):
    service = get_gmail_service()
    return (
        service.users()
        .messages()
        .modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]},
        )
        .execute()
    )


def send_reply_with_attachment(
    thread_id: str,
    to_address: str,
    original_subject: str,
    body_text: str,
    pdf_path: str | None,
    in_reply_to: str | None = None,
):
    """
    Reply in the same thread with a text body and optional single PDF attachment.
    """
    service = get_gmail_service()

    subject = original_subject
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    message = EmailMessage()
    message["To"] = extract_email_address(to_address)
    message["Subject"] = subject
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
        message["References"] = in_reply_to
    message.set_content(body_text)

    # Attach PDF only if provided
    if pdf_path:
        with open(pdf_path, "rb") as f:
            pdf_data = f.read()
        filename = os.path.basename(pdf_path)
        message.add_attachment(
            pdf_data,
            maintype="application",
            subtype="pdf",
            filename=filename,
        )

    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    send_body = {
        "raw": encoded_message,
        "threadId": thread_id,
    }

    sent = (
        service.users()
        .messages()
        .send(userId="me", body=send_body)
        .execute()
    )

    return sent
