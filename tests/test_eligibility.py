from reachai.skills.eligibility import EligibilitySkill


def test_eligibility_accepts_targeted_roles():
    skill = EligibilitySkill()
    ok, reason = skill.check({"title": "Hiring Manager", "blocked": False, "already_contacted": False}, {"score": 90})
    assert ok is True
    assert reason == "eligible"


def test_eligibility_rejects_blocked_target():
    skill = EligibilitySkill()
    ok, reason = skill.check({"title": "Founder", "blocked": True, "already_contacted": False}, {"score": 90})
    assert ok is False
    assert reason == "blocked"
