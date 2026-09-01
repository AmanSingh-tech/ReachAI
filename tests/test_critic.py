from reachai.skills.critic import CriticSkill


def test_critic_rejects_missing_resume_link():
    skill = CriticSkill()
    result = skill.review({"message": "Hi there, I would love to connect."}, {"company": "ExampleAI"})
    assert result["passed"] is False
    assert "missing_resume_link" in result["issues"]
