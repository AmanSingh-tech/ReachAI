from __future__ import annotations

import base64
import json
import os
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


class GmailClient:
    """Gmail client with OAuth2 configuration and a test-friendly in-memory mode."""

    def __init__(self, credentials: Dict[str, Any] | None = None):
        self.credentials = credentials or {}
        self.message_history: List[Dict[str, Any]] = []
        self.credentials_path: str | None = None
        self.token_path: str | None = None
        self.service = None
        self._configured = False
        self.scopes = os.getenv(
            "GMAIL_SCOPES",
            "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.modify",
        ).split()

    def configure_from_env(self) -> bool:
        """Read Gmail OAuth config from environment variables."""
        self.credentials_path = os.getenv("GMAIL_CREDENTIALS_PATH")
        self.token_path = os.getenv("GMAIL_TOKEN_PATH")
        self.scopes = os.getenv(
            "GMAIL_SCOPES",
            "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.modify",
        ).split()
        if self.credentials_path and os.path.exists(self.credentials_path):
            self.credentials = json.loads(Path(self.credentials_path).read_text(encoding="utf-8"))
            self._configured = True
            return True
        self._configured = False
        return False

    def oauth_configured(self) -> bool:
        """Whether OAuth configuration is present."""
        return bool(self._configured or (self.credentials_path and os.path.exists(self.credentials_path)))

    def _build_service(self):
        """Build a Gmail API service from OAuth credentials or raise a clear error."""
        if not self.configure_from_env() and not self.credentials:
            raise RuntimeError(
                "Gmail OAuth is not configured. Set GMAIL_CREDENTIALS_PATH and GMAIL_TOKEN_PATH in your environment."
            )

        if self.token_path and os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    raise RuntimeError(
                        "Gmail token is invalid or expired. Re-run OAuth authorization to refresh it."
                    )
            self.service = build("gmail", "v1", credentials=creds)
            return self.service

        flow = InstalledAppFlow.from_client_config(self.credentials, self.scopes)
        creds = flow.run_local_server(port=0)
        if self.token_path:
            Path(self.token_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, "w", encoding="utf-8") as fh:
                fh.write(creds.to_json())
        self.service = build("gmail", "v1", credentials=creds)
        return self.service

    def send_approval_request(self, recipient: str, subject: str, body: str, approval_token: str) -> Dict[str, Any]:
        """Send an approval request email with approval/reject links."""
        if self.oauth_configured():
            try:
                service = self._build_service()
                msg = EmailMessage()
                msg["To"] = recipient
                msg["From"] = "me"
                msg["Subject"] = subject
                msg.set_content(body)
                payload = {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")}
                service.users().messages().send(userId="me", body=payload).execute()
                return {
                    "status": "sent",
                    "recipient": recipient,
                    "subject": subject,
                    "approval_token": approval_token,
                    "channel": "gmail_oauth",
                }
            except Exception:
                return {
                    "status": "queued",
                    "recipient": recipient,
                    "subject": subject,
                    "approval_token": approval_token,
                    "channel": "gmail_oauth",
                }
        return {
            "status": "queued",
            "recipient": recipient,
            "subject": subject,
            "approval_token": approval_token,
        }

    def send_outreach(self, recipient: str, subject: str, body: str) -> Dict[str, Any]:
        """Send an approved outreach message."""
        if self.oauth_configured():
            try:
                service = self._build_service()
                msg = EmailMessage()
                msg["To"] = recipient
                msg["From"] = "me"
                msg["Subject"] = subject
                msg.set_content(body)
                payload = {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")}
                sent = service.users().messages().send(userId="me", body=payload).execute()
                return {
                    "status": "sent",
                    "recipient": recipient,
                    "subject": subject,
                    "message_id": sent.get("id"),
                    "channel": "gmail_oauth",
                }
            except Exception:
                return {
                    "status": "queued",
                    "recipient": recipient,
                    "subject": subject,
                    "message_id": f"msg-{id(body)}",
                    "channel": "gmail_oauth",
                }
        return {
            "status": "queued",
            "recipient": recipient,
            "subject": subject,
            "message_id": f"msg-{id(body)}",
        }

    def get_new_messages(self, query: str = "is:unread") -> List[Dict[str, Any]]:
        """Poll for new messages matching the query."""
        if self.message_history:
            return list(self.message_history)
        if not self.oauth_configured():
            return []

        try:
            service = self._build_service()
            response = service.users().messages().list(userId="me", q=query).execute()
            messages = response.get("messages", [])
            items = []
            for message in messages:
                msg = service.users().messages().get(userId="me", id=message["id"], format="full").execute()
                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                payload = msg.get("payload", {})
                body_data = ""
                if payload.get("parts"):
                    for part in payload["parts"]:
                        if part.get("mimeType") == "text/plain":
                            body_data = part.get("body", {}).get("data", "")
                            break
                if not body_data:
                    body_data = payload.get("body", {}).get("data", "")
                if body_data:
                    decoded = base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")
                else:
                    decoded = ""
                items.append({
                    "id": message["id"],
                    "from": headers.get("From", ""),
                    "subject": headers.get("Subject", ""),
                    "body": decoded,
                })
            return items
        except Exception:
            return []

    def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read after processing."""
        if self.oauth_configured():
            try:
                service = self._build_service()
                service.users().messages().modify(
                    userId="me",
                    id=message_id,
                    body={"removeLabelIds": ["UNREAD"]},
                ).execute()
                return True
            except Exception:
                return False
        return True

    def _add_message_for_testing(self, message: Dict[str, Any]) -> None:
        """Helper for tests to inject messages into the polling queue."""
        self.message_history.append(message)

