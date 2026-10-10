"""Pydantic contracts for institution-managed interviews."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

InstitutionRole = Literal["institution_admin", "faculty", "student"]
QuestionType = Literal["hr", "technical", "mcq"]


class MembershipOut(BaseModel):
    membership_id: str
    institution_id: str
    institution_name: str
    institution_slug: str
    role: InstitutionRole
    batch: Optional[str] = None
    branch: Optional[str] = None


class MemberCreate(BaseModel):
    email: str
    name: Optional[str] = None
    role: InstitutionRole
    batch: Optional[str] = None
    branch: Optional[str] = None

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value:
            raise ValueError("A valid email is required")
        return value


class MemberOut(BaseModel):
    membership_id: str
    user_id: str
    email: str
    name: Optional[str]
    role: InstitutionRole
    batch: Optional[str]
    branch: Optional[str]


class QuestionIn(BaseModel):
    question_text: str
    question_type: QuestionType
    mcq_options: Optional[list[str]] = None
    mcq_correct_index: Optional[int] = None
    max_score: float = Field(default=10.0, gt=0, le=100)

    @field_validator("question_text")
    @classmethod
    def question_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question text is required")
        return value

    @model_validator(mode="after")
    def validate_mcq(self):
        if self.question_type == "mcq":
            if not self.mcq_options or len(self.mcq_options) < 2:
                raise ValueError("MCQs require at least two options")
            if any(not option.strip() for option in self.mcq_options):
                raise ValueError("MCQ options cannot be empty")
            if self.mcq_correct_index is None or not 0 <= self.mcq_correct_index < len(self.mcq_options):
                raise ValueError("MCQ correct answer must reference an option")
        elif self.mcq_options is not None or self.mcq_correct_index is not None:
            raise ValueError("Only MCQs may define options or a correct answer")
        return self


class RoundIn(BaseModel):
    title: str
    questions: list[QuestionIn]

    @field_validator("title")
    @classmethod
    def title_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Round title is required")
        return value.strip()

    @field_validator("questions")
    @classmethod
    def questions_required(cls, value: list[QuestionIn]) -> list[QuestionIn]:
        if not value:
            raise ValueError("Each round needs at least one question")
        return value


class InterviewWrite(BaseModel):
    title: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    duration_minutes: int = Field(gt=0, le=480)
    deadline: Optional[datetime] = None
    eligible_batches: list[str] = Field(default_factory=list)
    eligible_branches: list[str] = Field(default_factory=list)
    rounds: list[RoundIn]

    @field_validator("title")
    @classmethod
    def interview_title_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Interview title is required")
        return value.strip()

    @field_validator("rounds")
    @classmethod
    def rounds_required(cls, value: list[RoundIn]) -> list[RoundIn]:
        if not value:
            raise ValueError("At least one round is required")
        return value


class AnswerSave(BaseModel):
    answer_text: Optional[str] = None
    selected_option_index: Optional[int] = Field(default=None, ge=0)


class InstitutionSelection(BaseModel):
    institution_id: str
