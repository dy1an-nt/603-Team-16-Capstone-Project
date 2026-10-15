import pytest
from pydantic import ValidationError

from app.schemas import AnalysisCreate, RevisionUpdate, SuggestionList


def test_llm_cannot_set_review_fields():
    raw = (
        '{"suggestions": [{"section": "experience", "original": "a", "revised": "b",'
        ' "reason": "r", "accepted": true, "flagged": false}]}'
    )
    draft = SuggestionList.model_validate_json(raw).suggestions[0]
    assert "accepted" not in draft.model_dump()
    assert "flagged" not in draft.model_dump()


def test_blank_job_description_rejected():
    with pytest.raises(ValidationError):
        AnalysisCreate(resume_id=1, job_description="   ")
    assert AnalysisCreate(resume_id=1).job_description is None


def test_duplicate_decision_index_rejected():
    with pytest.raises(ValidationError):
        RevisionUpdate(decisions=[{"index": 0, "accepted": True}, {"index": 0, "accepted": False}])
    assert len(RevisionUpdate(decisions=[{"index": 0, "accepted": True}]).decisions) == 1
