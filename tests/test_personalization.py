from reachai.skills.personalization import PersonalizationSkill


def test_personalization_includes_resume_and_company_context():
    skill = PersonalizationSkill()
    draft = skill.generate(
        {"name": "Aman Singh", "resume_url": "https://example.com/resume", "experience": ["LLM workflows", "product engineering"]},
        {"name": "Sarah Chen", "company": "Northstar Labs"},
        {"title": "AI Engineer"},
        {"company_summary": "AI tooling company"},
        92,
    )
    assert draft["should_contact"] is True
    assert "Northstar Labs" in draft["message"]
    assert "https://example.com/resume" in draft["message"]
