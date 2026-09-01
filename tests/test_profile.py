from reachai.models.candidate import CandidateProfile


def test_candidate_profile_validates_min_fields():
    candidate = CandidateProfile(
        name="Aman Singh",
        resume_url="https://example.com/resume",
        skills=["Python", "LLMs"],
        strengths=["AI systems"],
        target_roles=["AI Engineer"],
    )

    assert candidate.name == "Aman Singh"
    assert candidate.resume_url.startswith("https://")
