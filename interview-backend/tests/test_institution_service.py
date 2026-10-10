"""Focused institution authorization, persistence, scoring, and concurrency guards."""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from database import Base
from models import (
    Institution,
    InstitutionInterview,
    InstitutionInterviewQuestion,
    InstitutionInterviewRound,
    InstitutionMembership,
    User,
)
from services.gemini_service import GeminiService, InstitutionEvaluation
from services.institution_service import (
    Conflict,
    Expired,
    Forbidden,
    get_attempt,
    get_interview,
    require_membership,
    save_answer,
    start_attempt,
    submit_attempt,
)
from routes import institution as institution_routes
from fastapi import HTTPException


@pytest_asyncio.fixture
async def seeded(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'institution.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        inst_a = Institution(name="Alpha University", slug="alpha")
        inst_b = Institution(name="Beta University", slug="beta")
        admin = User(email="admin@alpha.edu", name="Admin")
        student = User(email="student@alpha.edu", name="Student")
        outsider = User(email="student@beta.edu", name="Outsider")
        db.add_all([inst_a, inst_b, admin, student, outsider]); await db.flush()
        admin_membership = InstitutionMembership(institution_id=inst_a.id, user_id=admin.id, role="institution_admin", is_verified=True)
        student_membership = InstitutionMembership(institution_id=inst_a.id, user_id=student.id, role="student", batch="2026", branch="CSE", is_verified=True)
        outsider_membership = InstitutionMembership(institution_id=inst_b.id, user_id=outsider.id, role="student", batch="2026", branch="CSE", is_verified=True)
        db.add_all([admin_membership, student_membership, outsider_membership])
        interview = InstitutionInterview(
            institution_id=inst_a.id, created_by_user_id=admin.id, title="Placement Mock",
            duration_minutes=30, status="published", published_at=datetime.utcnow(),
            eligible_batches=["2026"], eligible_branches=["CSE"],
        )
        round_ = InstitutionInterviewRound(title="Faculty Round", position=0)
        round_.questions = [
            InstitutionInterviewQuestion(question_text="Explain dependency injection.", question_type="technical", position=0, max_score=10),
            InstitutionInterviewQuestion(question_text="Which value is two?", question_type="mcq", position=1, mcq_options=["one", "two", "three"], mcq_correct_index=1, max_score=10),
        ]
        interview.rounds = [round_]
        db.add(interview); await db.commit()
        yield db, {"inst_a":inst_a, "inst_b":inst_b, "admin":admin, "student":student, "outsider":outsider,
                   "student_membership":student_membership, "outsider_membership":outsider_membership, "interview":interview,
                   "sessions": sessions}
    await engine.dispose()


@pytest.mark.asyncio
async def test_cross_institution_membership_is_rejected(seeded):
    db, x = seeded
    with pytest.raises(Forbidden):
        await require_membership(db, x["outsider"].id, x["inst_a"].id)


@pytest.mark.asyncio
async def test_eligibility_is_enforced(seeded):
    db, x = seeded
    x["student_membership"].branch = "ECE"
    await db.commit()
    interview = await get_interview(db, x["interview"].id)
    with pytest.raises(Forbidden):
        await start_attempt(db, interview, x["student_membership"])


@pytest.mark.asyncio
async def test_duplicate_start_returns_same_attempt(seeded):
    db, x = seeded
    interview = await get_interview(db, x["interview"].id)
    first = await start_attempt(db, interview, x["student_membership"])
    second = await start_attempt(db, interview, x["student_membership"])
    assert first.id == second.id


@pytest.mark.asyncio
async def test_concurrent_start_still_creates_one_attempt(seeded):
    db, x = seeded
    await db.close()

    async def begin():
        async with x["sessions"]() as other_db:
            membership = await other_db.get(InstitutionMembership, x["student_membership"].id)
            interview = await get_interview(other_db, x["interview"].id)
            return (await start_attempt(other_db, interview, membership)).id

    first, second = await asyncio.gather(begin(), begin())
    assert first == second


@pytest.mark.asyncio
async def test_student_cannot_submit_another_students_attempt(seeded):
    db, x = seeded
    attempt = await start_attempt(db, await get_interview(db, x["interview"].id), x["student_membership"])
    with pytest.raises(Forbidden):
        await submit_attempt(db, attempt.id, x["outsider"].id)


@pytest.mark.asyncio
async def test_exact_stored_question_and_mcq_scoring(seeded, monkeypatch):
    db, x = seeded
    interview = await get_interview(db, x["interview"].id)
    attempt = await start_attempt(db, interview, x["student_membership"])
    attempt = await get_attempt(db, attempt.id)
    free_text, mcq = attempt.interview.rounds[0].questions
    evaluator = AsyncMock(return_value=InstitutionEvaluation(score=8, feedback="Good explanation"))
    monkeypatch.setattr(GeminiService, "evaluate_institution_answer", evaluator)
    await save_answer(db, attempt, free_text.id, "It supplies dependencies from outside.", None)
    attempt = await get_attempt(db, attempt.id)
    await save_answer(db, attempt, mcq.id, None, 1)
    result = await submit_attempt(db, attempt.id, x["student"].id)
    evaluator.assert_awaited_once_with("Explain dependency injection.", "It supplies dependencies from outside.")
    scores = {a.question_id: a.score for a in result.answers}
    assert scores[free_text.id] == 8
    assert scores[mcq.id] == 10
    assert result.overall_score_percentage == 90


@pytest.mark.asyncio
async def test_expired_attempt_rejects_answer_updates(seeded):
    db, x = seeded
    attempt = await start_attempt(db, await get_interview(db, x["interview"].id), x["student_membership"])
    attempt.expires_at = datetime.utcnow() - timedelta(seconds=1)
    await db.commit()
    attempt = await get_attempt(db, attempt.id)
    question = attempt.interview.rounds[0].questions[0]
    with pytest.raises(Expired):
        await save_answer(db, attempt, question.id, "Too late", None)


@pytest.mark.asyncio
async def test_duplicate_submission_is_rejected(seeded, monkeypatch):
    db, x = seeded
    attempt = await start_attempt(db, await get_interview(db, x["interview"].id), x["student_membership"])
    monkeypatch.setattr(GeminiService, "evaluate_institution_answer", AsyncMock(return_value=InstitutionEvaluation(score=5, feedback="OK")))
    await submit_attempt(db, attempt.id, x["student"].id)
    with pytest.raises(Conflict):
        await submit_attempt(db, attempt.id, x["student"].id)


@pytest.mark.asyncio
async def test_proxy_secret_is_required_before_identity_is_trusted(seeded, monkeypatch):
    db, _ = seeded
    monkeypatch.setattr(institution_routes, "PROXY_SECRET", "server-only-secret")
    with pytest.raises(HTTPException) as exc:
        await institution_routes.current_principal(
            db=db,
            internal_secret="browser-forged-secret",
            verified_email="attacker@example.com",
            verified_name="Attacker",
        )
    assert exc.value.status_code == 401
