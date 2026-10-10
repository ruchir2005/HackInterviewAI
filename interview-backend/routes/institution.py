"""Institution interview API, reachable only through the authenticated Next.js proxy."""
import hmac
import os
from urllib.parse import unquote
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models import (
    InstitutionInterview,
    InstitutionInterviewAttempt,
    InstitutionInterviewRound,
    InstitutionMembership,
    User,
)
from schemas.institution import AnswerSave, InterviewWrite, MemberCreate
from services.institution_service import (
    Conflict,
    Forbidden,
    InstitutionError,
    NotFound,
    STAFF_ROLES,
    attempt_out,
    create_interview,
    get_attempt,
    get_interview,
    interview_out,
    is_eligible,
    memberships_for,
    publish_interview,
    replace_interview_content,
    require_membership,
    resolve_principal,
    retry_evaluation,
    save_answer,
    start_attempt,
    submit_attempt,
)

router = APIRouter(prefix="/api/institution", tags=["institution"])
PROXY_SECRET = os.getenv("INSTITUTION_PROXY_SECRET") or os.getenv("ADMIN_PROXY_SECRET")


async def current_principal(
    db: AsyncSession = Depends(get_db),
    internal_secret: Optional[str] = Header(None, alias="X-Internal-Institution-Secret"),
    verified_email: Optional[str] = Header(None, alias="X-Verified-User-Email"),
    verified_name: Optional[str] = Header(None, alias="X-Verified-User-Name"),
):
    if not PROXY_SECRET or not internal_secret or not hmac.compare_digest(internal_secret, PROXY_SECRET):
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not verified_email:
        raise HTTPException(status_code=401, detail="Verified user identity is missing")
    return await resolve_principal(db, verified_email, unquote(verified_name) if verified_name else None)


def handle(error: InstitutionError):
    raise HTTPException(status_code=error.status_code, detail=str(error))


@router.get("/memberships")
async def list_my_memberships(principal=Depends(current_principal), db: AsyncSession = Depends(get_db)):
    memberships = await memberships_for(db, principal.user.id)
    return [
        {
            "membership_id": m.id,
            "institution_id": m.institution_id,
            "institution_name": m.institution.name,
            "institution_slug": m.institution.slug,
            "role": m.role,
            "batch": m.batch,
            "branch": m.branch,
        }
        for m in memberships
    ]


@router.get("/{institution_id}/dashboard")
async def dashboard(institution_id: str, principal=Depends(current_principal), db: AsyncSession = Depends(get_db)):
    try:
        membership = await require_membership(db, principal.user.id, institution_id)
    except InstitutionError as exc:
        handle(exc)

    if membership.role == "student":
        interviews = list((await db.execute(
            select(InstitutionInterview)
            .options(selectinload(InstitutionInterview.rounds).selectinload(InstitutionInterviewRound.questions))
            .where(
                InstitutionInterview.institution_id == institution_id,
                InstitutionInterview.status == "published",
            )
            .order_by(InstitutionInterview.deadline.asc().nullslast(), InstitutionInterview.created_at.desc())
        )).scalars().unique().all())
        interviews = [item for item in interviews if is_eligible(membership, item)]
        attempts = list((await db.execute(
            select(InstitutionInterviewAttempt).where(
                InstitutionInterviewAttempt.student_user_id == principal.user.id,
                InstitutionInterviewAttempt.interview_id.in_([i.id for i in interviews]) if interviews else False,
            )
        )).scalars().all()) if interviews else []
        attempt_map = {a.interview_id: a for a in attempts}
        return {
            "institution": {"id": membership.institution.id, "name": membership.institution.name},
            "membership": {"role": membership.role, "batch": membership.batch, "branch": membership.branch},
            "interviews": [
                {
                    **interview_out(item, include_key=False),
                    "attempt": (
                        {
                            "id": attempt_map[item.id].id,
                            "status": attempt_map[item.id].status,
                            "expires_at": attempt_map[item.id].expires_at,
                            "score": attempt_map[item.id].overall_score_percentage,
                        }
                        if item.id in attempt_map else None
                    ),
                }
                for item in interviews
            ],
        }

    interviews = list((await db.execute(
        select(InstitutionInterview)
        .options(selectinload(InstitutionInterview.rounds).selectinload(InstitutionInterviewRound.questions))
        .where(InstitutionInterview.institution_id == institution_id)
        .order_by(InstitutionInterview.created_at.desc())
    )).scalars().unique().all())
    members = list((await db.execute(
        select(InstitutionMembership)
        .options(selectinload(InstitutionMembership.user))
        .where(InstitutionMembership.institution_id == institution_id)
    )).scalars().all())
    attempt_counts = dict((await db.execute(
        select(InstitutionInterviewAttempt.interview_id, func.count(InstitutionInterviewAttempt.id))
        .where(InstitutionInterviewAttempt.interview_id.in_([i.id for i in interviews]) if interviews else False)
        .group_by(InstitutionInterviewAttempt.interview_id)
    )).all()) if interviews else {}
    return {
        "institution": {"id": membership.institution.id, "name": membership.institution.name},
        "membership": {"role": membership.role, "batch": membership.batch, "branch": membership.branch},
        "interviews": [
            {**interview_out(item, include_key=True), "attempt_count": attempt_counts.get(item.id, 0)}
            for item in interviews
        ],
        "members": [
            {"membership_id": m.id, "user_id": m.user_id, "email": m.user.email, "name": m.user.name,
             "role": m.role, "batch": m.batch, "branch": m.branch}
            for m in members
        ],
    }


@router.post("/{institution_id}/members", status_code=201)
async def add_member(
    institution_id: str, payload: MemberCreate,
    principal=Depends(current_principal), db: AsyncSession = Depends(get_db),
):
    try:
        await require_membership(db, principal.user.id, institution_id, {"institution_admin"})
    except InstitutionError as exc:
        handle(exc)
    user = (await db.execute(select(User).where(func.lower(User.email) == payload.email))).scalar_one_or_none()
    if user is None:
        user = User(email=payload.email, name=payload.name, provider="institution_invite")
        db.add(user)
        await db.flush()
    existing = (await db.execute(select(InstitutionMembership).where(
        InstitutionMembership.institution_id == institution_id,
        InstitutionMembership.user_id == user.id,
    ))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="That user is already a member of this institution")
    membership = InstitutionMembership(
        institution_id=institution_id, user_id=user.id, role=payload.role,
        batch=payload.batch, branch=payload.branch, is_verified=True,
    )
    db.add(membership)
    await db.commit()
    return {"membership_id": membership.id, "email": user.email, "role": membership.role}


@router.post("/{institution_id}/interviews", status_code=201)
async def create_institution_interview(
    institution_id: str, payload: InterviewWrite,
    principal=Depends(current_principal), db: AsyncSession = Depends(get_db),
):
    try:
        await require_membership(db, principal.user.id, institution_id, STAFF_ROLES)
        interview = await create_interview(db, institution_id, principal.user.id, payload)
        return interview_out(interview, include_key=True)
    except InstitutionError as exc:
        handle(exc)


@router.get("/{institution_id}/interviews/{interview_id}")
async def read_institution_interview(
    institution_id: str, interview_id: str,
    principal=Depends(current_principal), db: AsyncSession = Depends(get_db),
):
    try:
        membership = await require_membership(db, principal.user.id, institution_id)
        interview = await get_interview(db, interview_id)
        if interview.institution_id != institution_id:
            raise NotFound("Institution interview not found")
        if membership.role == "student" and (interview.status != "published" or not is_eligible(membership, interview)):
            raise Forbidden("This interview is not available to you")
        return interview_out(interview, include_key=membership.role in STAFF_ROLES)
    except InstitutionError as exc:
        handle(exc)


@router.put("/{institution_id}/interviews/{interview_id}")
async def update_institution_interview(
    institution_id: str, interview_id: str, payload: InterviewWrite,
    principal=Depends(current_principal), db: AsyncSession = Depends(get_db),
):
    try:
        await require_membership(db, principal.user.id, institution_id, STAFF_ROLES)
        interview = await get_interview(db, interview_id)
        if interview.institution_id != institution_id:
            raise NotFound("Institution interview not found")
        return interview_out(await replace_interview_content(db, interview, payload), include_key=True)
    except InstitutionError as exc:
        handle(exc)


@router.post("/{institution_id}/interviews/{interview_id}/publish")
async def publish_institution_interview(
    institution_id: str, interview_id: str,
    principal=Depends(current_principal), db: AsyncSession = Depends(get_db),
):
    try:
        await require_membership(db, principal.user.id, institution_id, STAFF_ROLES)
        interview = await get_interview(db, interview_id)
        if interview.institution_id != institution_id:
            raise NotFound("Institution interview not found")
        return interview_out(await publish_interview(db, interview), include_key=True)
    except InstitutionError as exc:
        handle(exc)


@router.post("/{institution_id}/interviews/{interview_id}/attempts")
async def begin_attempt(
    institution_id: str, interview_id: str,
    principal=Depends(current_principal), db: AsyncSession = Depends(get_db),
):
    try:
        membership = await require_membership(db, principal.user.id, institution_id, {"student"})
        interview = await get_interview(db, interview_id)
        if interview.institution_id != institution_id:
            raise NotFound("Institution interview not found")
        attempt = await start_attempt(db, interview, membership)
        return attempt_out(await get_attempt(db, attempt.id))
    except InstitutionError as exc:
        handle(exc)


@router.get("/attempts/{attempt_id}")
async def read_attempt(attempt_id: str, principal=Depends(current_principal), db: AsyncSession = Depends(get_db)):
    try:
        attempt = await get_attempt(db, attempt_id)
        membership = await require_membership(db, principal.user.id, attempt.interview.institution_id)
        if membership.role == "student" and attempt.student_user_id != principal.user.id:
            raise Forbidden("Students may access only their own attempts")
        return attempt_out(attempt)
    except InstitutionError as exc:
        handle(exc)


@router.put("/attempts/{attempt_id}/answers/{question_id}")
async def persist_answer(
    attempt_id: str, question_id: str, payload: AnswerSave,
    principal=Depends(current_principal), db: AsyncSession = Depends(get_db),
):
    try:
        attempt = await get_attempt(db, attempt_id)
        if attempt.student_user_id != principal.user.id:
            raise Forbidden("Students may edit only their own attempt")
        await require_membership(db, principal.user.id, attempt.interview.institution_id, {"student"})
        answer = await save_answer(db, attempt, question_id, payload.answer_text, payload.selected_option_index)
        return {"id": answer.id, "question_id": answer.question_id, "saved_at": answer.saved_at}
    except InstitutionError as exc:
        handle(exc)


@router.post("/attempts/{attempt_id}/submit")
async def finalize_attempt(attempt_id: str, principal=Depends(current_principal), db: AsyncSession = Depends(get_db)):
    try:
        attempt = await submit_attempt(db, attempt_id, principal.user.id)
        return attempt_out(attempt)
    except InstitutionError as exc:
        handle(exc)


@router.get("/{institution_id}/interviews/{interview_id}/reports")
async def interview_reports(
    institution_id: str, interview_id: str,
    principal=Depends(current_principal), db: AsyncSession = Depends(get_db),
):
    try:
        await require_membership(db, principal.user.id, institution_id, STAFF_ROLES)
        interview = await get_interview(db, interview_id)
        if interview.institution_id != institution_id:
            raise NotFound("Institution interview not found")
    except InstitutionError as exc:
        handle(exc)
    students = list((await db.execute(
        select(InstitutionMembership)
        .options(selectinload(InstitutionMembership.user))
        .where(InstitutionMembership.institution_id == institution_id, InstitutionMembership.role == "student")
    )).scalars().all())
    students = [m for m in students if is_eligible(m, interview)]
    attempts = list((await db.execute(
        select(InstitutionInterviewAttempt).where(InstitutionInterviewAttempt.interview_id == interview_id)
    )).scalars().all())
    by_user = {a.student_user_id: a for a in attempts}
    return {
        "interview": {"id": interview.id, "title": interview.title},
        "assigned_students": len(students),
        "completed_count": sum(1 for a in attempts if a.status in {"completed", "evaluation_failed"}),
        "students": [
            {
                "user_id": m.user_id, "name": m.user.name, "email": m.user.email,
                "batch": m.batch, "branch": m.branch,
                "attempt": ({"id": by_user[m.user_id].id, "status": by_user[m.user_id].status,
                             "score": by_user[m.user_id].overall_score_percentage}
                            if m.user_id in by_user else None),
            }
            for m in students
        ],
    }


@router.post("/{institution_id}/attempts/{attempt_id}/retry-evaluation")
async def retry_attempt_evaluation(
    institution_id: str, attempt_id: str,
    principal=Depends(current_principal), db: AsyncSession = Depends(get_db),
):
    try:
        await require_membership(db, principal.user.id, institution_id, STAFF_ROLES)
        attempt = await get_attempt(db, attempt_id)
        if attempt.interview.institution_id != institution_id:
            raise NotFound("Institution interview attempt not found")
        return attempt_out(await retry_evaluation(db, attempt_id))
    except InstitutionError as exc:
        handle(exc)
