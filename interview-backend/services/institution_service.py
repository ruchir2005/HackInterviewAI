"""Authorization and business logic for institution-managed interviews."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import (
    Institution,
    InstitutionInterview,
    InstitutionInterviewAnswer,
    InstitutionInterviewAttempt,
    InstitutionInterviewQuestion,
    InstitutionInterviewRound,
    InstitutionMembership,
    User,
)
from schemas.institution import InterviewWrite
from services.gemini_service import GeminiService

STAFF_ROLES = {"institution_admin", "faculty"}


class InstitutionError(Exception):
    status_code = 400


class NotFound(InstitutionError):
    status_code = 404


class Forbidden(InstitutionError):
    status_code = 403


class Conflict(InstitutionError):
    status_code = 409


class Expired(InstitutionError):
    status_code = 409


@dataclass
class Principal:
    user: User


async def resolve_principal(db: AsyncSession, email: str, name: Optional[str]) -> Principal:
    normalized = email.strip().lower()
    user = (await db.execute(select(User).where(func.lower(User.email) == normalized))).scalar_one_or_none()
    if user is None:
        user = User(email=normalized, name=name, provider="google")
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif name and user.name != name:
        user.name = name
        await db.commit()
    return Principal(user=user)


async def memberships_for(db: AsyncSession, user_id: str) -> list[InstitutionMembership]:
    result = await db.execute(
        select(InstitutionMembership)
        .options(selectinload(InstitutionMembership.institution))
        .join(Institution, Institution.id == InstitutionMembership.institution_id)
        .where(InstitutionMembership.user_id == user_id, InstitutionMembership.is_verified.is_(True))
        .order_by(Institution.name)
    )
    return list(result.scalars().all())


async def require_membership(
    db: AsyncSession, user_id: str, institution_id: str, roles: Optional[set[str]] = None
) -> InstitutionMembership:
    result = await db.execute(
        select(InstitutionMembership)
        .options(selectinload(InstitutionMembership.institution))
        .where(
            InstitutionMembership.user_id == user_id,
            InstitutionMembership.institution_id == institution_id,
            InstitutionMembership.is_verified.is_(True),
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise Forbidden("You do not have a verified membership in this institution")
    if roles and membership.role not in roles:
        raise Forbidden("Your institution role does not allow this action")
    return membership


def interview_stmt():
    return select(InstitutionInterview).options(
        selectinload(InstitutionInterview.rounds).selectinload(InstitutionInterviewRound.questions),
        selectinload(InstitutionInterview.institution),
    )


async def get_interview(db: AsyncSession, interview_id: str) -> InstitutionInterview:
    interview = (await db.execute(interview_stmt().where(InstitutionInterview.id == interview_id))).scalar_one_or_none()
    if interview is None:
        raise NotFound("Institution interview not found")
    return interview


def is_eligible(membership: InstitutionMembership, interview: InstitutionInterview) -> bool:
    batches = [b.strip().lower() for b in (interview.eligible_batches or []) if b]
    branches = [b.strip().lower() for b in (interview.eligible_branches or []) if b]
    student_batch = membership.batch.strip().lower() if membership.batch else None
    student_branch = membership.branch.strip().lower() if membership.branch else None
    return (not batches or student_batch in batches) and (not branches or student_branch in branches)


def question_out(question: InstitutionInterviewQuestion, include_key: bool = False) -> dict:
    data = {
        "id": question.id,
        "question_text": question.question_text,
        "question_type": question.question_type,
        "position": question.position,
        "mcq_options": question.mcq_options if question.question_type == "mcq" else None,
        "max_score": question.max_score,
    }
    if include_key:
        data["mcq_correct_index"] = question.mcq_correct_index
    return data


def interview_out(interview: InstitutionInterview, include_key: bool = False) -> dict:
    return {
        "id": interview.id,
        "institution_id": interview.institution_id,
        "title": interview.title,
        "description": interview.description,
        "instructions": interview.instructions,
        "duration_minutes": interview.duration_minutes,
        "deadline": interview.deadline,
        "eligible_batches": interview.eligible_batches or [],
        "eligible_branches": interview.eligible_branches or [],
        "status": interview.status,
        "published_at": interview.published_at,
        "rounds": [
            {
                "id": round_.id,
                "title": round_.title,
                "position": round_.position,
                "questions": [question_out(q, include_key) for q in sorted(round_.questions, key=lambda x: x.position)],
            }
            for round_ in sorted(interview.rounds, key=lambda x: x.position)
        ],
    }


async def replace_interview_content(
    db: AsyncSession, interview: InstitutionInterview, payload: InterviewWrite
) -> InstitutionInterview:
    if interview.status != "draft":
        raise Conflict("Published interviews are locked and cannot be edited")
    interview.title = payload.title
    interview.description = payload.description
    interview.instructions = payload.instructions
    interview.duration_minutes = payload.duration_minutes
    deadline = payload.deadline
    if deadline and deadline.tzinfo is not None:
        deadline = deadline.astimezone(timezone.utc).replace(tzinfo=None)
    interview.deadline = deadline
    interview.eligible_batches = [x.strip() for x in payload.eligible_batches if x.strip()]
    interview.eligible_branches = [x.strip() for x in payload.eligible_branches if x.strip()]

    # Eagerly load the rounds collection before mutating it so SQLAlchemy
    # does not attempt a synchronous lazy load (which raises MissingGreenlet
    # in an async context, particularly on newly-created interviews).
    await db.refresh(interview, ["rounds"])
    interview.rounds.clear()
    await db.flush()
    for round_position, round_payload in enumerate(payload.rounds):
        round_row = InstitutionInterviewRound(title=round_payload.title, position=round_position)
        round_row.questions = [
            InstitutionInterviewQuestion(
                question_text=q.question_text,
                question_type=q.question_type,
                position=question_position,
                mcq_options=q.mcq_options,
                mcq_correct_index=q.mcq_correct_index,
                max_score=q.max_score,
            )
            for question_position, q in enumerate(round_payload.questions)
        ]
        interview.rounds.append(round_row)
    await db.commit()
    return await get_interview(db, interview.id)


async def create_interview(
    db: AsyncSession, institution_id: str, creator_id: str, payload: InterviewWrite
) -> InstitutionInterview:
    interview = InstitutionInterview(
        institution_id=institution_id,
        created_by_user_id=creator_id,
        title=payload.title,
        duration_minutes=payload.duration_minutes,
        status="draft",
    )
    db.add(interview)
    await db.flush()
    # Build nested rows through the same validated replacement path.
    return await replace_interview_content(db, interview, payload)


async def publish_interview(db: AsyncSession, interview: InstitutionInterview) -> InstitutionInterview:
    if interview.status == "published":
        return interview
    if not interview.rounds or any(not round_.questions for round_ in interview.rounds):
        raise Conflict("An interview needs at least one non-empty round before publishing")
    interview.status = "published"
    interview.published_at = datetime.utcnow()
    await db.commit()
    return await get_interview(db, interview.id)


async def start_attempt(
    db: AsyncSession, interview: InstitutionInterview, membership: InstitutionMembership
) -> InstitutionInterviewAttempt:
    # Keep scalar identifiers before a possible rollback. A failed flush expires
    # ORM instances, so reading their attributes afterward can trigger async IO.
    interview_id = interview.id
    student_user_id = membership.user_id
    if membership.role != "student":
        raise Forbidden("Only student memberships can start an interview attempt")
    if interview.status != "published":
        raise Forbidden("This interview is not published")
    now = datetime.utcnow()
    if interview.deadline and now > interview.deadline:
        raise Expired("The interview deadline has passed")
    if not is_eligible(membership, interview):
        raise Forbidden("This interview is not available for your batch or branch")

    existing = (await db.execute(
        select(InstitutionInterviewAttempt).where(
            InstitutionInterviewAttempt.interview_id == interview_id,
            InstitutionInterviewAttempt.student_user_id == student_user_id,
        )
    )).scalar_one_or_none()
    if existing:
        return existing

    expires = now + timedelta(minutes=interview.duration_minutes)
    if interview.deadline and interview.deadline < expires:
        expires = interview.deadline
    attempt = InstitutionInterviewAttempt(
        interview_id=interview_id,
        student_user_id=student_user_id,
        status="in_progress",
        started_at=now,
        expires_at=expires,
    )
    db.add(attempt)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = (await db.execute(
            select(InstitutionInterviewAttempt).where(
                InstitutionInterviewAttempt.interview_id == interview_id,
                InstitutionInterviewAttempt.student_user_id == student_user_id,
            )
        )).scalar_one()
        return existing
    await db.refresh(attempt)
    return attempt


async def get_attempt(db: AsyncSession, attempt_id: str) -> InstitutionInterviewAttempt:
    result = await db.execute(
        select(InstitutionInterviewAttempt)
        .options(
            selectinload(InstitutionInterviewAttempt.answers),
            selectinload(InstitutionInterviewAttempt.interview)
            .selectinload(InstitutionInterview.rounds)
            .selectinload(InstitutionInterviewRound.questions),
        )
        .where(InstitutionInterviewAttempt.id == attempt_id)
        .execution_options(populate_existing=True)
    )
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise NotFound("Institution interview attempt not found")
    return attempt


async def save_answer(
    db: AsyncSession,
    attempt: InstitutionInterviewAttempt,
    question_id: str,
    answer_text: Optional[str],
    selected_option_index: Optional[int],
) -> InstitutionInterviewAnswer:
    if attempt.status != "in_progress":
        raise Conflict("This attempt no longer accepts answers")
    if datetime.utcnow() >= attempt.expires_at:
        raise Expired("This attempt has expired; submit it to finalize the saved answers")
    questions = {q.id: q for r in attempt.interview.rounds for q in r.questions}
    question = questions.get(question_id)
    if question is None:
        raise Forbidden("This question does not belong to the attempt's interview")
    if question.question_type == "mcq":
        if selected_option_index is not None and not 0 <= selected_option_index < len(question.mcq_options or []):
            raise InstitutionError("Selected MCQ option is invalid")
        answer_text = None
    else:
        selected_option_index = None

    answer = (await db.execute(select(InstitutionInterviewAnswer).where(
        InstitutionInterviewAnswer.attempt_id == attempt.id,
        InstitutionInterviewAnswer.question_id == question_id,
    ))).scalar_one_or_none()
    if answer is None:
        answer = InstitutionInterviewAnswer(attempt_id=attempt.id, question_id=question_id)
        db.add(answer)
    answer.answer_text = answer_text
    answer.selected_option_index = selected_option_index
    answer.score = None
    answer.feedback = None
    answer.evaluation_status = "pending"
    answer.evaluation_error = None
    await db.commit()
    await db.refresh(answer)
    return answer


async def _evaluate_attempt_answers(db: AsyncSession, attempt_id: str, only_failed: bool = False) -> InstitutionInterviewAttempt:
    attempt = await get_attempt(db, attempt_id)
    answer_by_question = {a.question_id: a for a in attempt.answers}
    failed = False
    for round_ in attempt.interview.rounds:
        for question in round_.questions:
            answer = answer_by_question.get(question.id)
            if answer is None:
                continue
            if only_failed and answer.evaluation_status not in {"failed", "pending"}:
                continue
            if question.question_type == "mcq":
                answer.score = question.max_score if answer.selected_option_index == question.mcq_correct_index else 0.0
                answer.feedback = "Correct answer." if answer.score else "Incorrect answer."
                answer.evaluation_status = "completed"
                answer.evaluation_error = None
            elif not (answer.answer_text or "").strip():
                answer.score = 0.0
                answer.feedback = "No answer was submitted."
                answer.evaluation_status = "completed"
                answer.evaluation_error = None
            else:
                try:
                    result = await GeminiService.evaluate_institution_answer(
                        question.question_text, answer.answer_text or ""
                    )
                    answer.score = round((result.score / 10.0) * question.max_score, 2)
                    answer.feedback = result.feedback
                    answer.evaluation_status = "completed"
                    answer.evaluation_error = None
                except Exception as exc:
                    answer.score = None
                    answer.feedback = None
                    answer.evaluation_status = "failed"
                    answer.evaluation_error = "AI evaluation failed; faculty may retry."
                    failed = True

    total_max = sum(q.max_score for r in attempt.interview.rounds for q in r.questions)
    awarded = sum((a.score or 0.0) for a in attempt.answers if a.score is not None)
    attempt.overall_score_percentage = None if failed else round((awarded / total_max * 100) if total_max else 0.0, 2)
    attempt.status = "evaluation_failed" if failed else "completed"
    await db.commit()
    return await get_attempt(db, attempt.id)


async def submit_attempt(db: AsyncSession, attempt_id: str, user_id: str) -> InstitutionInterviewAttempt:
    # Row lock makes the in_progress -> evaluation_pending transition atomic.
    locked = (await db.execute(
        select(InstitutionInterviewAttempt)
        .where(InstitutionInterviewAttempt.id == attempt_id)
        .with_for_update()
    )).scalar_one_or_none()
    if locked is None:
        raise NotFound("Institution interview attempt not found")
    if locked.student_user_id != user_id:
        raise Forbidden("Students may submit only their own attempt")
    if locked.status != "in_progress":
        raise Conflict("This attempt has already been submitted")
    locked.status = "evaluation_pending"
    locked.submitted_at = datetime.utcnow()
    await db.commit()
    return await _evaluate_attempt_answers(db, attempt_id)


async def retry_evaluation(db: AsyncSession, attempt_id: str) -> InstitutionInterviewAttempt:
    attempt = await get_attempt(db, attempt_id)
    if attempt.status not in {"evaluation_failed", "evaluation_pending"}:
        raise Conflict("This attempt has no failed or pending evaluation")
    attempt.status = "evaluation_pending"
    await db.commit()
    return await _evaluate_attempt_answers(db, attempt_id, only_failed=True)


def attempt_out(attempt: InstitutionInterviewAttempt, include_answers: bool = True) -> dict:
    answers = {a.question_id: a for a in attempt.answers}
    result = {
        "id": attempt.id,
        "interview_id": attempt.interview_id,
        "student_user_id": attempt.student_user_id,
        "status": attempt.status,
        "started_at": attempt.started_at,
        "expires_at": attempt.expires_at,
        "submitted_at": attempt.submitted_at,
        "overall_score_percentage": attempt.overall_score_percentage,
        "server_time": datetime.utcnow(),
        "interview": interview_out(attempt.interview, include_key=False),
    }
    if include_answers:
        result["answers"] = [
            {
                "id": answer.id,
                "question_id": answer.question_id,
                "answer_text": answer.answer_text,
                "selected_option_index": answer.selected_option_index,
                "score": answer.score,
                "feedback": answer.feedback,
                "evaluation_status": answer.evaluation_status,
            }
            for answer in answers.values()
        ]
    return result
