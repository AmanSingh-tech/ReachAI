from reachai.skills.approval import ApprovalSkill


def test_approval_token_is_single_use():
    skill = ApprovalSkill()
    token = skill.create_token("draft-1")

    assert skill.validate_token(token) is True
    assert skill.approve(token) is True
    assert skill.validate_token(token) is False
    assert skill.approve(token) is False
