from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


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
