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


DEFAULT_SCOPES = "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.modify"


class GmailClient:
    """Gmail client with OAuth2 configuration and a test-friendly in-memory mode."""

    def __init__(self, credentials: Dict[str, Any] | None = None):
        self.credentials = credentials or {}
        self.message_history: List[Dict[str, Any]] = []
        self.credentials_path: str | None = None
        self.token_path: str | None = None
        self.service = None
        self._configured = False
        self.scopes = os.getenv("GMAIL_SCOPES", DEFAULT_SCOPES).split()

    def configure_from_env(self) -> bool:
        """Read Gmail OAuth config from environment variables."""
        self.credentials_path = os.getenv("GMAIL_CREDENTIALS_PATH")
        self.token_path = os.getenv("GMAIL_TOKEN_PATH")
        self.scopes = os.getenv("GMAIL_SCOPES", DEFAULT_SCOPES).split()
        if self.credentials_path and os.path.exists(self.credentials_path):
            self.credentials = json.loads(Path(self.credentials_path).read_text(encoding="utf-8"))
            self._configured = True
            return True
        self._configured = False
        return False

    def oauth_configured(self) -> bool:
        """Whether OAuth client configuration is present."""
        if not self._configured and self.credentials_path is None:
            self.configure_from_env()
        return bool(self._configured or (self.credentials_path and os.path.exists(self.credentials_path)))

    def authorized(self) -> bool:
        """Whether the one-time browser consent has produced a token file."""
        return self.oauth_configured() and bool(self.token_path and os.path.exists(self.token_path))

    def authorize(self) -> str:
        """Run the browser consent flow once and store the token. Returns the account address."""
        if not self.configure_from_env():
            raise RuntimeError("Set GMAIL_CREDENTIALS_PATH to your downloaded OAuth client JSON first.")
        if not self.token_path:
            raise RuntimeError("Set GMAIL_TOKEN_PATH to where the token should be stored.")
        flow = InstalledAppFlow.from_client_config(self.credentials, self.scopes)
        creds = flow.run_local_server(port=0)
        Path(self.token_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.token_path).write_text(creds.to_json(), encoding="utf-8")
        os.chmod(self.token_path, 0o600)
        self.service = build("gmail", "v1", credentials=creds)
        return self.account_email()

    def account_email(self) -> str:
        service = self._build_service()
        return service.users().getProfile(userId="me").execute().get("emailAddress", "")

    def _build_service(self):
        """Build a Gmail API service from a stored token, or raise a clear error.

        Never opens a browser: background runs must not block on consent.
        """
        if self.service is not None:
            return self.service
        if not self.configure_from_env():
            raise RuntimeError("Gmail OAuth is not configured. Set GMAIL_CREDENTIALS_PATH and GMAIL_TOKEN_PATH.")
        if not self.token_path or not os.path.exists(self.token_path):
            raise RuntimeError("Gmail is not authorized yet. Run `reachai auth-gmail` once.")
        creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                Path(self.token_path).write_text(creds.to_json(), encoding="utf-8")
            else:
                raise RuntimeError("Gmail token is invalid. Run `reachai auth-gmail` again.")
        self.service = build("gmail", "v1", credentials=creds)
        return self.service

    def _send(self, recipient: str, subject: str, body: str, html: str | None = None) -> Dict[str, Any]:
        msg = EmailMessage()
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.set_content(body)
        if html:
            msg.add_alternative(html, subtype="html")
        payload = {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")}
        try:
            sent = self._build_service().users().messages().send(userId="me", body=payload).execute()
        except Exception as exc:
            return {"status": "failed", "recipient": recipient, "subject": subject, "error": str(exc)}
        return {
            "status": "sent",
            "recipient": recipient,
            "subject": subject,
            "message_id": sent.get("id"),
            "channel": "gmail_oauth",
        }

    def send_approval_request(
        self, recipient: str, subject: str, body: str, approval_token: str, html: str | None = None
    ) -> Dict[str, Any]:
        """Email the owner a draft to approve."""
        result = self._send(recipient, subject, body, html)
        result["approval_token"] = approval_token
        return result

    def send_outreach(self, recipient: str, subject: str, body: str) -> Dict[str, Any]:
        """Send an approved outreach message. ``status`` is ``sent`` only when Gmail accepted it."""
        return self._send(recipient, subject, body)

    @staticmethod
    def _plain_text(payload: Dict[str, Any]) -> str:
        if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"] + "==").decode("utf-8", errors="replace")
        for part in payload.get("parts", []) or []:
            text = GmailClient._plain_text(part)
            if text:
                return text
        return ""

    def get_new_messages(self, query: str = "is:unread") -> List[Dict[str, Any]]:
        """Return messages matching ``query`` with sender, subject and plain-text body."""
        if self.message_history:
            return list(self.message_history)
        if not self.authorized():
            return []

        service = self._build_service()
        response = service.users().messages().list(userId="me", q=query, maxResults=50).execute()
        items = []
        for message in response.get("messages", []):
            msg = service.users().messages().get(userId="me", id=message["id"], format="full").execute()
            payload = msg.get("payload", {})
            headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
            items.append({
                "id": message["id"],
                "from": headers.get("from", ""),
                "subject": headers.get("subject", ""),
                "body": self._plain_text(payload),
            })
        return items

    def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read after processing."""
        if not self.authorized():
            return True
        try:
            self._build_service().users().messages().modify(
                userId="me",
                id=message_id,
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()
            return True
        except Exception:
            return False

    def _add_message_for_testing(self, message: Dict[str, Any]) -> None:
        """Helper for tests to inject messages into the polling queue."""
        self.message_history.append(message)
