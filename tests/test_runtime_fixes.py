from reachai.cli import cmd_outreach
from reachai.integrations.llm import LLMClient
from reachai.skills.personalization import PersonalizationSkill
from reachai.storage.database import Database


def test_database_default_path_follows_settings(tmp_path, monkeypatch):
    db_path = tmp_path / "configured.db"
    monkeypatch.setenv("REACHAI_DB_PATH", str(db_path))
    assert Database().db_path == db_path
    assert db_path.exists()


def test_cli_outreach_requires_a_stored_target(tmp_path):
    result = cmd_outreach(str(tmp_path / "cli.db"))
    assert result["status"] == "target_required"


def test_llm_client_ignores_placeholder_keys_and_never_returns_canned_text():
    client = LLMClient(api_key="your_openai_api_key_here", backend="openrouter")
    assert client.client is None
    assert client.generate("anything") == {}


def test_personalization_uses_only_profile_facts():
    draft = PersonalizationSkill().generate(
        {
            "name": "Aman Singh",
            "resume_url": "https://example.com/resume",
            "skills": ["Python", "LLMs", "Go"],
            "experience": ["Google Web Solutions Engineer Intern"],
        },
        {"name": "Sarah Chen", "company": "Northstar Labs"},
        {"title": "AI Engineer", "description": "Python and LLM agents"},
    )
    message = draft["message"]
    assert "I work with Python and LLMs." in message
    assert "Go." not in message and "and Go" not in message
    assert "the Google Web Solutions Engineer Intern role." in message
