from datetime import date

from pydantic import BaseModel, Field


class StudentCreate(BaseModel):
    name: str
    roll_number: str
    admission_date: date | None = None
    parent_name: str | None = None
    mobile_number: str | None = None
    grade: str | None = Field(default=None, max_length=20)
    section: str | None = Field(default=None, max_length=20)
    status: str = Field(default="active", max_length=20)


class StudentUpdate(BaseModel):
    name: str | None = None
    roll_number: str | None = None
    admission_date: date | None = None
    parent_name: str | None = None
    mobile_number: str | None = None
    grade: str | None = Field(default=None, max_length=20)
    section: str | None = Field(default=None, max_length=20)
    status: str | None = Field(default=None, max_length=20)


class StudentResponse(BaseModel):
    id: int
    name: str
    roll_number: str
    admission_date: date | None = None
    parent_name: str | None = None
    mobile_number: str | None = None
    grade: str | None = None
    section: str | None = None
    status: str
    created_at: str | None = None