from datetime import time

from pydantic import BaseModel, Field


class TimetableCreate(BaseModel):
    section_id: int
    subject_id: int
    staff_id: int

    day_of_week: int = Field(
        ge=1,
        le=7,
        description="1 = Monday, 7 = Sunday"
    )

    start_time: time
    end_time: time

    room: str | None = None
    status: str = "active"


class TimetableUpdate(BaseModel):
    section_id: int | None = None
    subject_id: int | None = None
    staff_id: int | None = None

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
    subject_id: int
    staff_id: int
    day_of_week: int
    start_time: time
    end_time: time
    room: str | None
    status: str