import json

from reachai.integrations.gmail import GmailClient


def test_gmail_client_detects_oauth_configuration(tmp_path, monkeypatch):
    credentials = tmp_path / "credentials.json"
    credentials.write_text(json.dumps({
        "installed": {
            "client_id": "abc",
            "client_secret": "def",
            "redirect_uris": ["http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }))

    monkeypatch.setenv("GMAIL_CREDENTIALS_PATH", str(credentials))
    monkeypatch.setenv("GMAIL_TOKEN_PATH", str(tmp_path / "token.json"))

    client = GmailClient()
    client.configure_from_env()

    assert client.oauth_configured() is True
    assert client.credentials_path == str(credentials)
    assert client.token_path == str(tmp_path / "token.json")
