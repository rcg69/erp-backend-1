from datetime import date, time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClassSessionCreate(BaseModel):
    timetable_id: int
    subject_id: int
    staff_id: int
    session_date: date
    is_conducted: bool = False
    remarks: Optional[str] = None


class ClassSessionUpdate(BaseModel):
    timetable_id: Optional[int] = None
    subject_id: Optional[int] = None
    staff_id: Optional[int] = None
    session_date: Optional[date] = None
    is_conducted: Optional[bool] = None
    remarks: Optional[str] = None


class ClassSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timetable_id: int
    subject_id: int
    staff_id: int
    session_date: date
    is_conducted: bool
    remarks: Optional[str] = None


class SessionGenerateRequest(BaseModel):
    """
    Generate dated class sessions from a class + section's weekly grid.

    start_date / end_date default to the range stored on the grid.
    skip_dates is for holidays.
    """

    grade_id: int
    section_id: int
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    skip_dates: list[date] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_date_range(self):
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end_date must be on or after start_date")
        return self


class SessionGenerateResponse(BaseModel):
    success: bool
    message: str
    created: int
    assigned_slots: int
    unassigned_slots: int
    start_date: date
    end_date: date


class ClassDaySession(BaseModel):
    """
    One period of a class's timetable on a specific date, with its dated
    class session (if it could be created).

    ready = False means the slot has no subject and/or staff assigned yet,
    so no class session can exist for it.
    """

    timetable_id: int
    period_number: Optional[int] = None
    day_of_week: int
    start_time: time
    end_time: time
    default_subject_id: Optional[int] = None
    default_staff_id: Optional[int] = None

    session_id: Optional[int] = None
    subject_id: Optional[int] = None
    staff_id: Optional[int] = None
    is_conducted: bool = False
    ready: bool


class ClassDaySessionsResponse(BaseModel):
    grade_id: int
    section_id: int
    session_date: date
    day_of_week: int
    sessions: list[ClassDaySession]