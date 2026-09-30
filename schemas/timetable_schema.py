from datetime import date, time

from pydantic import BaseModel, Field, model_validator


class TimetableCreate(BaseModel):
    section_id: int
    grade_id: int | None = None

    day_of_week: int = Field(
        ge=1,
        le=7,
        description="1 = Monday, 7 = Sunday"
    )

    period_number: int | None = Field(default=None, ge=1, le=12)

    start_time: time
    end_time: time

    room: str | None = None
    status: str = "active"


class TimetableUpdate(BaseModel):
    section_id: int | None = None

    day_of_week: int | None = Field(
        default=None,
        ge=1,
        le=7
    )

    start_time: time | None = None
    end_time: time | None = None

    room: str | None = None
    status: str | None = None


class TimetableResponse(BaseModel):
    id: int
    section_id: int
    grade_id: int | None = None
    day_of_week: int
    period_number: int | None = None
    start_time: time
    end_time: time
    room: str | None = None
    status: str
    default_subject_id: int | None = None
    default_staff_id: int | None = None
    valid_from: date | None = None
    valid_to: date | None = None


class TimetableOpenRequest(BaseModel):
    """Create (or re-open) the 6 x 6 grid for one class + section."""

    grade_id: int
    section_id: int
    valid_from: date
    valid_to: date

    @model_validator(mode="after")
    def check_date_range(self):
        if self.valid_to < self.valid_from:
            raise ValueError("valid_to must be on or after valid_from")
        return self


class TimetableAssignment(BaseModel):
    """
    Weekly subject/staff for one slot.
    Send null to clear a value.
    """

    subject_id: int | None = None
    staff_id: int | None = None