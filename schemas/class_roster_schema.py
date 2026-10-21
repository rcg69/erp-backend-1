from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ClassRosterStudent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None = None
    name: str
    roll_number: str
    admission_date: date | None = None
    parent_name: str | None = None
    mobile_number: str | None = None
    grade: str | None = None
    section: str | None = None
    status: str
    created_at: datetime | None = None


class ClassRosterResponse(BaseModel):
    academic_year: str
    grade: str
    section: str
    count: int
    students: list[ClassRosterStudent]
