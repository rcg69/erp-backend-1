from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


ExamStatus = Literal["draft", "scheduled", "completed", "published"]
EvaluationStatus = Literal["pending", "in_progress", "completed"]


class ExamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    academic_year: str = Field(min_length=1, max_length=20)
    grade_id: int = Field(gt=0)
    description: str | None = None
    start_date: date
    end_date: date

    @field_validator("name", "academic_year")
    @classmethod
    def strip_required_text(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class ExamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None):
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class ExamResponse(BaseModel):
    id: int
    name: str
    academic_year: str
    grade_id: int
    grade: str | None = None
    section_id: int | None = None
    section: str | None = None
    description: str | None = None
    start_date: date
    end_date: date
    status: ExamStatus
    created_by: int
    created_at: datetime
    updated_at: datetime


class ExamSubjectCreate(BaseModel):
    subject_id: int = Field(gt=0)
    max_marks: Decimal = Field(gt=0, max_digits=8, decimal_places=2)
    pass_marks: Decimal = Field(ge=0, max_digits=8, decimal_places=2)
    exam_date: date | None = None
    evaluator_staff_id: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_pass_marks(self):
        if self.pass_marks > self.max_marks:
            raise ValueError("pass_marks cannot exceed max_marks")
        return self


class ExamSubjectUpdate(BaseModel):
    max_marks: Decimal | None = Field(
        default=None, gt=0, max_digits=8, decimal_places=2
    )
    pass_marks: Decimal | None = Field(
        default=None, ge=0, max_digits=8, decimal_places=2
    )
    exam_date: date | None = None
    evaluator_staff_id: int | None = Field(default=None, gt=0)


class ExamSubjectResponse(BaseModel):
    id: int
    exam_id: int
    subject_id: int
    subject_code: str
    subject_name: str
    max_marks: Decimal
    pass_marks: Decimal
    exam_date: date | None = None
    evaluator_staff_id: int
    evaluator_name: str
    evaluation_status: EvaluationStatus
    student_count: int = 0
    marked_count: int = 0
    created_at: datetime
    updated_at: datetime


class StudentMarkEntry(BaseModel):
    marks_obtained: Decimal | None = Field(
        default=None, ge=0, max_digits=8, decimal_places=2
    )
    is_absent: bool = False
    remarks: str | None = Field(default=None, max_length=2000)


class StudentMarkResponse(BaseModel):
    student_id: int
    name: str
    roll_number: str
    marks_obtained: Decimal | None = None
    is_absent: bool
    remarks: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MarksCorrection(BaseModel):
    marks_obtained: Decimal | None = Field(
        default=None, ge=0, max_digits=8, decimal_places=2
    )
    is_absent: bool = False
    remarks: str | None = Field(default=None, max_length=2000)
    reason: str = Field(min_length=1, max_length=1000)


class EvaluationProgress(BaseModel):
    exam_subject_id: int
    exam_id: int
    evaluation_status: EvaluationStatus
    total_students: int
    marked_students: int
    pending_students: int


class PublishedStudentResult(BaseModel):
    exam_id: int
    exam_name: str
    academic_year: str
    status: ExamStatus
    student_id: int
    student_name: str
    roll_number: str
    subjects: list[dict]
