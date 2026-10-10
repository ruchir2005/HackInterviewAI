"""Add institution memberships and fixed-question interview workflow.

Revision ID: 0004_institution_interviews
Revises: 0003_assessment_active_flag
Create Date: 2026-10-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_institution_interviews"
down_revision = "0003_assessment_active_flag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("institutions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_institutions_slug"),
    )
    op.create_index("ix_institutions_slug", "institutions", ["slug"])

    op.create_table("institution_memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("batch", sa.String(100), nullable=True),
        sa.Column("branch", sa.String(100), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("institution_id", "user_id", name="uq_institution_membership_user"),
        sa.CheckConstraint("role IN ('institution_admin', 'faculty', 'student')", name="ck_institution_membership_role"),
    )
    op.create_index("ix_institution_memberships_institution_id", "institution_memberships", ["institution_id"])
    op.create_index("ix_institution_memberships_user_id", "institution_memberships", ["user_id"])

    op.create_table("institution_interviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("created_by_user_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("deadline", sa.DateTime(), nullable=True),
        sa.Column("eligible_batches", sa.JSON(), nullable=False),
        sa.Column("eligible_branches", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.CheckConstraint("duration_minutes > 0", name="ck_institution_interview_duration"),
        sa.CheckConstraint("status IN ('draft', 'published')", name="ck_institution_interview_status"),
    )
    op.create_index("ix_institution_interviews_institution_id", "institution_interviews", ["institution_id"])
    op.create_index("ix_institution_interviews_status", "institution_interviews", ["status"])
    op.create_index("ix_institution_interviews_deadline", "institution_interviews", ["deadline"])

    op.create_table("institution_interview_rounds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("interview_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["interview_id"], ["institution_interviews.id"]),
        sa.UniqueConstraint("interview_id", "position", name="uq_institution_round_position"),
        sa.CheckConstraint("position >= 0", name="ck_institution_round_position"),
    )
    op.create_index("ix_institution_interview_rounds_interview_id", "institution_interview_rounds", ["interview_id"])

    op.create_table("institution_interview_questions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("round_id", sa.String(36), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_type", sa.String(20), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("mcq_options", sa.JSON(), nullable=True),
        sa.Column("mcq_correct_index", sa.Integer(), nullable=True),
        sa.Column("max_score", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["round_id"], ["institution_interview_rounds.id"]),
        sa.UniqueConstraint("round_id", "position", name="uq_institution_question_position"),
        sa.CheckConstraint("position >= 0", name="ck_institution_question_position"),
        sa.CheckConstraint("max_score > 0", name="ck_institution_question_max_score"),
        sa.CheckConstraint("question_type IN ('hr', 'technical', 'mcq')", name="ck_institution_question_type"),
    )
    op.create_index("ix_institution_interview_questions_round_id", "institution_interview_questions", ["round_id"])

    op.create_table("institution_interview_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("interview_id", sa.String(36), nullable=False),
        sa.Column("student_user_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("overall_score_percentage", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["interview_id"], ["institution_interviews.id"]),
        sa.ForeignKeyConstraint(["student_user_id"], ["users.id"]),
        sa.UniqueConstraint("interview_id", "student_user_id", name="uq_institution_attempt_student"),
        sa.CheckConstraint("status IN ('in_progress', 'evaluation_pending', 'evaluation_failed', 'completed')", name="ck_institution_attempt_status"),
    )
    op.create_index("ix_institution_interview_attempts_interview_id", "institution_interview_attempts", ["interview_id"])
    op.create_index("ix_institution_interview_attempts_student_user_id", "institution_interview_attempts", ["student_user_id"])
    op.create_index("ix_institution_interview_attempts_status", "institution_interview_attempts", ["status"])
    op.create_index("ix_institution_interview_attempts_expires_at", "institution_interview_attempts", ["expires_at"])

    op.create_table("institution_interview_answers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("attempt_id", sa.String(36), nullable=False),
        sa.Column("question_id", sa.String(36), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("selected_option_index", sa.Integer(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("evaluation_status", sa.String(20), nullable=False),
        sa.Column("evaluation_error", sa.Text(), nullable=True),
        sa.Column("saved_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["institution_interview_attempts.id"]),
        sa.ForeignKeyConstraint(["question_id"], ["institution_interview_questions.id"]),
        sa.UniqueConstraint("attempt_id", "question_id", name="uq_institution_answer_question"),
        sa.CheckConstraint("selected_option_index IS NULL OR selected_option_index >= 0", name="ck_institution_answer_option_index"),
        sa.CheckConstraint("evaluation_status IN ('pending', 'completed', 'failed')", name="ck_institution_answer_evaluation_status"),
    )
    op.create_index("ix_institution_interview_answers_attempt_id", "institution_interview_answers", ["attempt_id"])
    op.create_index("ix_institution_interview_answers_question_id", "institution_interview_answers", ["question_id"])


def downgrade() -> None:
    for table, indexes in [
        ("institution_interview_answers", ["ix_institution_interview_answers_question_id", "ix_institution_interview_answers_attempt_id"]),
        ("institution_interview_attempts", ["ix_institution_interview_attempts_expires_at", "ix_institution_interview_attempts_status", "ix_institution_interview_attempts_student_user_id", "ix_institution_interview_attempts_interview_id"]),
        ("institution_interview_questions", ["ix_institution_interview_questions_round_id"]),
        ("institution_interview_rounds", ["ix_institution_interview_rounds_interview_id"]),
        ("institution_interviews", ["ix_institution_interviews_deadline", "ix_institution_interviews_status", "ix_institution_interviews_institution_id"]),
        ("institution_memberships", ["ix_institution_memberships_user_id", "ix_institution_memberships_institution_id"]),
        ("institutions", ["ix_institutions_slug"]),
    ]:
        for index in indexes:
            op.drop_index(index, table_name=table)
        op.drop_table(table)
