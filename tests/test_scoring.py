from reachai.skills.scoring import ScoringSkill


def test_scoring_returns_eligible_value_range():
    skill = ScoringSkill()
    score = skill.score_target(25, 20, 20, 20, 10, 5)
    assert 0 <= score <= 100
    assert score == 100


def test_job_score_ranks_ai_roles_highly():
    skill = ScoringSkill()
    result = skill.score_job({
        "title": "AI Engineer",
        "description": "Python, LLM workflows, RAG and AI agents",
    }, {"skills": ["Python", "LLMs", "RAG"], "strengths": ["AI systems"]})
    assert result >= 75
