from datetime import date

from pydantic import BaseModel


class ClassSessionCreate(BaseModel):
    timetable_id: int
    session_date: date
    is_conducted: bool = False
    remarks: str | None = None


class ClassSessionUpdate(BaseModel):
    timetable_id: int | None = None
    session_date: date | None = None
    is_conducted: bool | None = None
    remarks: str | None = None


class ClassSessionResponse(BaseModel):
    id: int
    timetable_id: int
    session_date: date
    is_conducted: bool
    remarks: str | None